"""Signed transport adapter for the Shopee Affiliate GraphQL API.

This module deliberately stops at the provider transport boundary.  Product
queries, pagination, and workflow integration belong to later adapters and
application layers.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests

from price_alert_skill import config


DEFAULT_SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TRANSIENT_RETRIES = 2
MAX_TRANSIENT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.5


class ShopeeErrorKind(str, Enum):
    """Provider error categories used by the bounded retry policy."""

    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    ACCESS = "access"
    BUSINESS = "business"
    TRANSIENT = "transient"
    NETWORK = "network"
    HTTP = "http"
    GRAPHQL = "graphql"
    RESPONSE = "response"
    CONFIGURATION = "configuration"


@dataclass(frozen=True)
class ShopeeErrorClassification:
    """Classification of a provider or transport failure."""

    kind: ShopeeErrorKind
    retryable: bool = False
    timestamp_retryable: bool = False

    @property
    def category(self) -> str:
        return self.kind.value


@dataclass(frozen=True)
class ShopeeGraphQLError:
    """Redacted, structured representation of one GraphQL error."""

    message: str
    code: int | None = None


class ShopeeConfigurationError(ValueError):
    """Raised before a request when the signed client is not configured."""


class ShopeeApiError(RuntimeError):
    """A redacted structured Shopee API, GraphQL, or transport failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: ShopeeErrorKind,
        code: int | None = None,
        status_code: int | None = None,
        retryable: bool = False,
        timestamp_retryable: bool = False,
        attempts: int = 1,
        graphql_errors: Sequence[ShopeeGraphQLError] = (),
        secrets: Sequence[str] = (),
    ) -> None:
        self.message = redact_secrets(message, secrets=secrets)
        self.kind = kind
        self.category = kind.value
        self.code = code
        self.status_code = status_code
        self.http_status = status_code
        self.error_code = code
        self.retryable = retryable
        self.is_retryable = retryable
        self.timestamp_retryable = timestamp_retryable
        self.attempts = attempts
        self.graphql_errors = tuple(graphql_errors)
        self.errors = self.graphql_errors

        parts = [f"Shopee {self.category} error"]
        if status_code is not None:
            parts.append(f"HTTP {status_code}")
        if code is not None:
            parts.append(f"code {code}")
        detail = self.message or "request failed"
        super().__init__(f"{' - '.join(parts)}: {detail}")


# Compatibility aliases make the provider boundary easy to consume without
# coupling later code to a particular spelling of "API".
ShopeeAPIError = ShopeeApiError


def redact_secrets(value: Any, *, secrets: Sequence[str] = ()) -> str:
    """Return text with credentials, signatures, and authorization values removed.

    Response messages are provider-controlled input.  Redaction is therefore
    applied both to configured secret values and to common credential-shaped
    fields, even when the caller did not provide a secret list.
    """

    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(str(secret), "[REDACTED]")

    text = re.sub(
        r"(?i)(authorization\s*:\s*)[^\r\n]+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(signature\s*[=:]\s*)[^,\s]+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)((?:app[_ -]?secret|client[_ -]?secret|secret)\s*[=:]\s*)[^,\s]+",
        r"\1[REDACTED]",
        text,
    )
    return text


# A more descriptive public name for callers that do not want to mention the
# implementation detail that only secrets are redacted.
redact_sensitive_data = redact_secrets


def serialize_payload(payload: Mapping[str, Any]) -> bytes:
    """Serialize a request exactly once into the bytes sent to Shopee."""

    try:
        serialized = json.dumps(
            dict(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ShopeeConfigurationError(
            f"Shopee request payload is not JSON serializable: {exc}"
        ) from exc
    return serialized.encode("utf-8")


def calculate_signature(
    app_id: str,
    timestamp: int | str,
    payload: bytes | str,
    app_secret: str,
) -> str:
    """Calculate the lowercase SHA-256 signature for an exact payload."""

    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
    factor = (
        str(app_id).encode("utf-8")
        + str(timestamp).encode("ascii")
        + payload_bytes
        + str(app_secret).encode("utf-8")
    )
    return hashlib.sha256(factor).hexdigest()


# Names used in the official documentation and useful to direct unit tests.
generate_signature = calculate_signature
build_signature = calculate_signature


def build_authorization_header(
    app_id: str,
    timestamp: int | str,
    signature: str,
) -> str:
    """Build the documented singular-``Credential`` Authorization value."""

    return (
        f"SHA256 Credential={app_id}, Timestamp={timestamp}, "
        f"Signature={signature}"
    )


def _is_timestamp_message(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "timestamp",
            "time stamp",
            "request expired",
            "expired request",
            "clock skew",
            "clock is",
            "request time",
        )
    )


def classify_shopee_error(
    code: int | None = None,
    message: str = "",
    *,
    status_code: int | None = None,
) -> ShopeeErrorClassification:
    """Classify documented Shopee codes and HTTP failures.

    Rate limiting is intentionally classified but not retried: the initial
    client has no configured wait/defer policy.  Timestamp failures get one
    special fresh-timestamp retry in :class:`ShopeeGraphQLClient`.
    """

    if status_code == 429:
        return ShopeeErrorClassification(ShopeeErrorKind.RATE_LIMIT)
    if status_code in {408, 425} or (status_code is not None and status_code >= 500):
        return ShopeeErrorClassification(ShopeeErrorKind.TRANSIENT, retryable=True)

    if code == 10020:
        return ShopeeErrorClassification(
            ShopeeErrorKind.AUTHENTICATION,
            timestamp_retryable=_is_timestamp_message(message),
        )
    if code == 10030:
        return ShopeeErrorClassification(ShopeeErrorKind.RATE_LIMIT)
    if code is not None and 10031 <= code <= 10035:
        return ShopeeErrorClassification(ShopeeErrorKind.ACCESS)
    if code is not None and 11000 <= code <= 11002:
        return ShopeeErrorClassification(ShopeeErrorKind.BUSINESS)
    if status_code is not None and status_code >= 400:
        return ShopeeErrorClassification(ShopeeErrorKind.HTTP)
    return ShopeeErrorClassification(ShopeeErrorKind.GRAPHQL)


classify_error = classify_shopee_error


def _coerce_error_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
    except (TypeError, ValueError):
        pass
    return None


def _code_from_message(message: str) -> int | None:
    match = re.search(r"\b(?:error\s*)?\[(\d+)\]", message, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_graphql_errors(
    response_body: Mapping[str, Any],
    *,
    secrets: Sequence[str] = (),
) -> tuple[ShopeeGraphQLError, ...]:
    """Extract GraphQL errors, including numeric codes from extensions/messages."""

    raw_errors = response_body.get("errors")
    if not isinstance(raw_errors, list):
        return ()

    parsed: list[ShopeeGraphQLError] = []
    for raw_error in raw_errors:
        if isinstance(raw_error, Mapping):
            raw_message = raw_error.get("message", "Shopee GraphQL request failed")
            message = redact_secrets(raw_message, secrets=secrets)
            extensions = raw_error.get("extensions")
            extension_code = (
                extensions.get("code")
                if isinstance(extensions, Mapping)
                else None
            )
            code = _coerce_error_code(extension_code) or _code_from_message(message)
        else:
            message = redact_secrets(
                "Shopee GraphQL request returned an invalid error entry",
                secrets=secrets,
            )
            code = None
        parsed.append(ShopeeGraphQLError(message=message, code=code))
    return tuple(parsed)


class ShopeeGraphQLClient:
    """Execute signed JSON GraphQL requests with bounded retry behavior."""

    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = DEFAULT_MAX_TRANSIENT_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        timestamp_factory: Callable[[], int | float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        session: Any | None = None,
        transport: Callable[..., Any] | None = None,
        logger: Callable[[str], None] | None = None,
        enabled: bool | None = None,
    ) -> None:
        settings = config.resolve_shopee_settings()
        credentials_supplied = app_id is not None or app_secret is not None

        # Explicit credentials are useful for isolated tests and are treated as
        # an explicit opt-in.  Config-loaded credentials are only read from the
        # settings object when SHOPEE_ENABLED is true.
        if enabled is None:
            resolved_enabled = settings.enabled if not credentials_supplied else True
        else:
            resolved_enabled = enabled
        if not resolved_enabled:
            raise ShopeeConfigurationError(
                "Shopee client is disabled; set SHOPEE_ENABLED=1 to enable it"
            )

        self.app_id = (app_id if app_id is not None else settings.app_id).strip()
        self.app_secret = (
            app_secret if app_secret is not None else settings.app_secret
        )
        if not self.app_id or not self.app_secret:
            raise ShopeeConfigurationError(
                "Shopee App ID and App Secret are required when Shopee is enabled"
            )

        self.api_url = (api_url or settings.api_url or DEFAULT_SHOPEE_API_URL).strip()
        if not self.api_url:
            raise ShopeeConfigurationError("Shopee API URL must not be empty")

        resolved_timeout = (
            settings.timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        try:
            self.timeout_seconds = float(resolved_timeout)
        except (TypeError, ValueError) as exc:
            raise ShopeeConfigurationError(
                "SHOPEE_REQUEST_TIMEOUT_SECONDS must be a positive number"
            ) from exc
        if self.timeout_seconds <= 0:
            raise ShopeeConfigurationError(
                "SHOPEE_REQUEST_TIMEOUT_SECONDS must be a positive number"
            )

        if isinstance(max_retries, bool) or max_retries < 0:
            raise ShopeeConfigurationError("max_retries must be zero or greater")
        self.max_retries = min(int(max_retries), MAX_TRANSIENT_RETRIES)

        if backoff_seconds < 0:
            raise ShopeeConfigurationError("backoff_seconds must be zero or greater")
        self.backoff_seconds = float(backoff_seconds)
        self._timestamp_factory = timestamp_factory or time.time
        self._sleeper = sleeper or time.sleep
        self._transport = transport or (session.post if session is not None else requests.post)
        self._logger = logger

    def execute(
        self,
        payload_or_query: Mapping[str, Any] | str | None = None,
        *,
        query: str | None = None,
        operation_name: str | None = None,
        variables: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one GraphQL payload and return the decoded successful response."""

        if payload_or_query is None:
            payload_or_query = query
        elif query is not None:
            raise ShopeeConfigurationError(
                "query cannot be combined with a payload mapping or query string"
            )
        payload = self._coerce_payload(
            payload_or_query,
            operation_name=operation_name,
            variables=variables,
        )
        serialized_payload = serialize_payload(payload)
        transient_retries = 0
        timestamp_retry_used = False
        request_count = 0

        while True:
            request_count += 1
            timestamp = int(self._timestamp_factory())
            signature = calculate_signature(
                self.app_id,
                timestamp,
                serialized_payload,
                self.app_secret,
            )
            headers = {
                "Content-Type": "application/json",
                "Authorization": build_authorization_header(
                    self.app_id,
                    timestamp,
                    signature,
                ),
            }

            try:
                response = self._transport(
                    self.api_url,
                    data=serialized_payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except (requests.exceptions.Timeout, TimeoutError) as exc:
                error = ShopeeApiError(
                    "request timed out",
                    kind=ShopeeErrorKind.NETWORK,
                    retryable=True,
                    attempts=request_count,
                    secrets=(self.app_secret, self.app_id),
                )
                if transient_retries < self.max_retries:
                    transient_retries += 1
                    self._wait_before_retry(transient_retries, error)
                    continue
                raise error from exc
            except (requests.exceptions.ConnectionError, ConnectionResetError) as exc:
                error = ShopeeApiError(
                    "connection failed",
                    kind=ShopeeErrorKind.NETWORK,
                    retryable=True,
                    attempts=request_count,
                    secrets=(self.app_secret, self.app_id),
                )
                if transient_retries < self.max_retries:
                    transient_retries += 1
                    self._wait_before_retry(transient_retries, error)
                    continue
                raise error from exc
            except requests.exceptions.RequestException as exc:
                error = ShopeeApiError(
                    "request failed",
                    kind=ShopeeErrorKind.NETWORK,
                    attempts=request_count,
                    secrets=(self.app_secret, self.app_id),
                )
                raise error from exc

            status_code = int(getattr(response, "status_code", 0) or 0)
            try:
                body = self._decode_response(response, request_count)
            except ShopeeApiError as decode_error:
                # A proxy or upstream can return an HTML/non-JSON body for a
                # temporary HTTP failure.  The status still determines the
                # retry class, so do not let decoding bypass bounded retries.
                if status_code in {408, 425} or status_code >= 500:
                    error = ShopeeApiError(
                        f"HTTP {status_code} response body was not valid JSON",
                        kind=ShopeeErrorKind.TRANSIENT,
                        status_code=status_code,
                        retryable=True,
                        attempts=request_count,
                        secrets=(self.app_secret, self.app_id),
                    )
                    if transient_retries < self.max_retries:
                        transient_retries += 1
                        self._wait_before_retry(transient_retries, error)
                        continue
                    raise error from decode_error
                if status_code == 429:
                    raise ShopeeApiError(
                        "HTTP 429 response body was not valid JSON",
                        kind=ShopeeErrorKind.RATE_LIMIT,
                        status_code=status_code,
                        attempts=request_count,
                        secrets=(self.app_secret, self.app_id),
                    ) from decode_error
                if status_code >= 400:
                    raise ShopeeApiError(
                        f"HTTP {status_code} response body was not valid JSON",
                        kind=ShopeeErrorKind.HTTP,
                        status_code=status_code,
                        attempts=request_count,
                        secrets=(self.app_secret, self.app_id),
                    ) from decode_error
                raise

            graphql_errors = parse_graphql_errors(
                body,
                secrets=(self.app_secret, self.app_id),
            )

            if status_code in {408, 425} or status_code >= 500:
                error = self._response_error(
                    body,
                    status_code=status_code,
                    request_count=request_count,
                    graphql_errors=graphql_errors,
                )
                if transient_retries < self.max_retries:
                    transient_retries += 1
                    self._wait_before_retry(transient_retries, error)
                    continue
                raise error

            if status_code == 429:
                raise self._response_error(
                    body,
                    status_code=status_code,
                    request_count=request_count,
                    graphql_errors=graphql_errors,
                )

            if status_code < 200 or status_code >= 300:
                raise self._response_error(
                    body,
                    status_code=status_code,
                    request_count=request_count,
                    graphql_errors=graphql_errors,
                )

            if "errors" in body and body.get("errors") is not None and not isinstance(
                body.get("errors"), list
            ):
                raise ShopeeApiError(
                    "response errors field was not a JSON array",
                    kind=ShopeeErrorKind.RESPONSE,
                    status_code=status_code,
                    attempts=request_count,
                    secrets=(self.app_secret, self.app_id),
                )

            if graphql_errors:
                primary = graphql_errors[0]
                classification = classify_shopee_error(
                    primary.code,
                    primary.message,
                    status_code=status_code,
                )
                if (
                    classification.timestamp_retryable
                    and not timestamp_retry_used
                ):
                    timestamp_retry_used = True
                    self._wait_before_retry(0, None)
                    continue
                raise ShopeeApiError(
                    primary.message,
                    kind=classification.kind,
                    code=primary.code,
                    status_code=status_code,
                    retryable=classification.retryable,
                    timestamp_retryable=classification.timestamp_retryable,
                    attempts=request_count,
                    graphql_errors=graphql_errors,
                    secrets=(self.app_secret, self.app_id),
                )

            if "data" not in body or body.get("data") is None:
                raise ShopeeApiError(
                    "response did not contain usable GraphQL data",
                    kind=ShopeeErrorKind.RESPONSE,
                    status_code=status_code,
                    attempts=request_count,
                    secrets=(self.app_secret, self.app_id),
                )
            return dict(body)

    def __repr__(self) -> str:
        """Avoid exposing the App Secret if an adapter is included in a log."""

        return (
            f"{type(self).__name__}(api_url={self.api_url!r}, "
            f"app_id='[REDACTED]', enabled=True)"
        )

    # Explicit aliases keep the adapter usable by callers that call the
    # operation a request or POST while retaining one implementation path.
    request = execute
    post = execute
    execute_query = execute

    @staticmethod
    def _coerce_payload(
        payload_or_query: Mapping[str, Any] | str | None,
        *,
        operation_name: str | None,
        variables: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(payload_or_query, Mapping):
            if operation_name is not None or variables is not None:
                raise ShopeeConfigurationError(
                    "operation_name and variables cannot be combined with a payload mapping"
                )
            return dict(payload_or_query)

        if not isinstance(payload_or_query, str) or not payload_or_query:
            raise ShopeeConfigurationError("Shopee GraphQL query must be a non-empty string")
        payload: dict[str, Any] = {"query": payload_or_query}
        if operation_name is not None:
            payload["operationName"] = operation_name
        if variables is not None:
            payload["variables"] = dict(variables)
        return payload

    def _decode_response(self, response: Any, request_count: int) -> dict[str, Any]:
        try:
            body = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            status_code = int(getattr(response, "status_code", 0) or 0)
            raise ShopeeApiError(
                "response body was not valid JSON",
                kind=ShopeeErrorKind.RESPONSE,
                status_code=status_code,
                attempts=request_count,
                secrets=(self.app_secret, self.app_id),
            ) from exc
        if not isinstance(body, Mapping):
            raise ShopeeApiError(
                "response body was not a JSON object",
                kind=ShopeeErrorKind.RESPONSE,
                status_code=int(getattr(response, "status_code", 0) or 0),
                attempts=request_count,
                secrets=(self.app_secret, self.app_id),
            )
        return dict(body)

    def _response_error(
        self,
        body: Mapping[str, Any],
        *,
        status_code: int,
        request_count: int,
        graphql_errors: Sequence[ShopeeGraphQLError],
    ) -> ShopeeApiError:
        primary = graphql_errors[0] if graphql_errors else None
        if primary is not None:
            message = primary.message
            code = primary.code
        else:
            raw_message = body.get("message") or body.get("error") or body.get("detail")
            if isinstance(raw_message, Mapping):
                raw_message = raw_message.get("message") or raw_message.get("detail")
            message = str(raw_message) if raw_message else f"HTTP {status_code} response"
            code = _coerce_error_code(body.get("code")) or _code_from_message(message)
        classification = classify_shopee_error(
            code,
            message,
            status_code=status_code,
        )
        return ShopeeApiError(
            message,
            kind=classification.kind,
            code=code,
            status_code=status_code,
            retryable=classification.retryable,
            timestamp_retryable=classification.timestamp_retryable,
            attempts=request_count,
            graphql_errors=graphql_errors,
            secrets=(self.app_secret, self.app_id),
        )

    def _wait_before_retry(
        self,
        retry_number: int,
        error: ShopeeApiError | None,
    ) -> None:
        if error is not None:
            self._log(
                f"Shopee {error.category} failure; retrying "
                f"(attempt {error.attempts + 1})"
            )
        if retry_number > 0:
            self._sleeper(self.backoff_seconds * (2 ** (retry_number - 1)))

    def _log(self, message: str) -> None:
        if self._logger is not None:
            self._logger(redact_secrets(message, secrets=(self.app_secret, self.app_id)))


ShopeeAPIClient = ShopeeGraphQLClient
