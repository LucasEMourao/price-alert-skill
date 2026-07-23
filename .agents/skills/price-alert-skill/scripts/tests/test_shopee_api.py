from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pytest
import requests

from price_alert_skill import config
from price_alert_skill.core.adapters.shopee_api import (
    ShopeeApiError,
    ShopeeConfigurationError,
    ShopeeErrorKind,
    ShopeeGraphQLClient,
    build_authorization_header,
    calculate_signature,
    classify_shopee_error,
    parse_graphql_errors,
    redact_secrets,
    serialize_payload,
)


@dataclass
class FakeResponse:
    status_code: int
    body: object

    def json(self):
        if isinstance(self.body, BaseException):
            raise self.body
        return self.body


def make_client(transport, **kwargs):
    return ShopeeGraphQLClient(
        app_id="123456",
        app_secret="unit-test-secret",
        enabled=True,
        api_url="https://example.invalid/graphql",
        transport=transport,
        sleeper=lambda _seconds: None,
        **kwargs,
    )


def test_signature_matches_the_authentication_documentation_vector():
    query = "{\nbrandOffer{\n    nodes{\n        commissionRate\n        offerName\n    }\n}\n}"
    payload = serialize_payload({"query": query})

    assert calculate_signature("123456", 1577836800, payload, "demo") == (
        "dc88d72feea70c80c52c3399751a7d34966763f51a7f056aa070a5e9df645412"
    )


def test_client_signs_and_sends_the_exact_serialized_body():
    calls = []

    def transport(url, *, data, headers, timeout):
        calls.append((url, data, headers, timeout))
        return FakeResponse(200, {"data": {"ok": True}})

    client = make_client(transport, timestamp_factory=lambda: 1577836800)
    payload = {"query": "{ ping }", "variables": {"name": "ação"}}

    result = client.execute(payload)

    assert result == {"data": {"ok": True}}
    assert len(calls) == 1
    url, transmitted_body, headers, timeout = calls[0]
    assert url == "https://example.invalid/graphql"
    assert transmitted_body == serialize_payload(payload)
    assert json.loads(transmitted_body) == payload
    expected_signature = calculate_signature(
        "123456", 1577836800, transmitted_body, "unit-test-secret"
    )
    assert headers == {
        "Content-Type": "application/json",
        "Authorization": build_authorization_header(
            "123456", 1577836800, expected_signature
        ),
    }
    assert "Credentials=" not in headers["Authorization"]
    assert timeout == 30.0


def test_query_convenience_payload_includes_optional_fields_without_reserializing():
    sent_bodies = []

    def transport(_url, *, data, headers, timeout):
        sent_bodies.append(data)
        return FakeResponse(200, {"data": {"ok": True}})

    client = make_client(transport, timestamp_factory=lambda: 10)
    client.execute("query { thing }", operation_name="Thing", variables={"x": 1})

    assert sent_bodies == [
        b'{"query":"query { thing }","operationName":"Thing","variables":{"x":1}}'
    ]


def test_missing_credentials_are_rejected_before_transport():
    with pytest.raises(ShopeeConfigurationError, match="App ID and App Secret"):
        ShopeeGraphQLClient(enabled=True, app_id="", app_secret="")


def test_disabled_configuration_does_not_load_credentials(monkeypatch):
    monkeypatch.setenv("SHOPEE_ENABLED", "0")
    monkeypatch.setenv("SHOPEE_APP_ID", "not-used")
    monkeypatch.setenv("SHOPEE_APP_SECRET", "not-used-secret")

    settings = config.resolve_shopee_settings()

    assert settings.enabled is False
    assert settings.app_id == ""
    assert settings.app_secret == ""


def test_timeout_retries_are_bounded_and_use_a_fresh_timestamp():
    timestamps = iter((100, 101, 102))
    calls = []

    def transport(_url, *, data, headers, timeout):
        calls.append(headers["Authorization"])
        if len(calls) < 3:
            raise requests.exceptions.Timeout("timeout")
        return FakeResponse(200, {"data": {"ok": True}})

    client = make_client(
        transport,
        max_retries=2,
        timestamp_factory=lambda: next(timestamps),
    )

    assert client.execute({"query": "{ ping }"})["data"] == {"ok": True}
    assert len(calls) == 3
    assert "Timestamp=100" in calls[0]
    assert "Timestamp=101" in calls[1]
    assert "Timestamp=102" in calls[2]


def test_connection_reset_is_transient_but_does_not_retry_forever():
    calls = 0

    def transport(_url, **_kwargs):
        nonlocal calls
        calls += 1
        raise requests.exceptions.ConnectionError("connection reset")

    client = make_client(transport, max_retries=2)

    with pytest.raises(ShopeeApiError) as raised:
        client.execute({"query": "{ ping }"})

    assert calls == 3
    assert raised.value.kind is ShopeeErrorKind.NETWORK
    assert raised.value.retryable is True


def test_temporary_http_5xx_is_retried_and_http_4xx_is_not():
    retry_calls = []

    def retry_transport(_url, **_kwargs):
        retry_calls.append(1)
        if len(retry_calls) == 1:
            return FakeResponse(503, {"message": "temporarily unavailable"})
        return FakeResponse(200, {"data": {"ok": True}})

    client = make_client(retry_transport, max_retries=1)
    assert client.execute({"query": "{ ping }"})["data"]["ok"] is True
    assert len(retry_calls) == 2

    client_error_calls = []

    def client_error_transport(_url, **_kwargs):
        client_error_calls.append(1)
        return FakeResponse(401, {"message": "invalid credentials"})

    with pytest.raises(ShopeeApiError) as raised:
        make_client(client_error_transport, max_retries=3).execute({"query": "{ ping }"})

    assert len(client_error_calls) == 1
    assert raised.value.status_code == 401
    assert raised.value.retryable is False


def test_http_200_graphql_10035_is_an_access_failure_and_not_retried():
    calls = []
    secret = "unit-test-secret"

    def transport(_url, **_kwargs):
        calls.append(1)
        return FakeResponse(
            200,
            {
                "data": None,
                "errors": [
                    {
                        "message": (
                            "error [10035]: access unavailable; secret=" + secret
                        ),
                        "extensions": {"code": 10035},
                    }
                ],
            },
        )

    with pytest.raises(ShopeeApiError) as raised:
        make_client(transport, max_retries=3).execute({"query": "{ ping }"})

    error = raised.value
    assert len(calls) == 1
    assert error.code == 10035
    assert error.kind is ShopeeErrorKind.ACCESS
    assert error.status_code == 200
    assert secret not in str(error)
    assert "Authorization" not in str(error)


def test_rate_limit_is_classified_without_an_implicit_wait_policy():
    classification = classify_shopee_error(10030, "rate limit exceeded")
    assert classification.kind is ShopeeErrorKind.RATE_LIMIT
    assert classification.retryable is False

    calls = []

    def transport(_url, **_kwargs):
        calls.append(1)
        return FakeResponse(
            200,
            {
                "data": None,
                "errors": [
                    {"message": "error [10030]: too many requests", "extensions": {"code": 10030}}
                ],
            },
        )

    with pytest.raises(ShopeeApiError) as raised:
        make_client(transport).execute({"query": "{ ping }"})
    assert len(calls) == 1
    assert raised.value.kind is ShopeeErrorKind.RATE_LIMIT
    assert raised.value.code == 10030


def test_timestamp_graphql_error_gets_one_fresh_timestamp_retry():
    timestamps = iter((200, 201))
    calls = []

    def transport(_url, *, headers, **_kwargs):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return FakeResponse(
                200,
                {
                    "data": None,
                    "errors": [
                        {
                            "message": "error [10020]: request timestamp expired",
                            "extensions": {"code": 10020},
                        }
                    ],
                },
            )
        return FakeResponse(200, {"data": {"ok": True}})

    client = make_client(
        transport,
        max_retries=0,
        timestamp_factory=lambda: next(timestamps),
    )

    assert client.execute({"query": "{ ping }"})["data"]["ok"] is True
    assert len(calls) == 2
    assert "Timestamp=200" in calls[0]
    assert "Timestamp=201" in calls[1]


def test_error_parser_retains_numeric_code_and_redaction():
    secret = "s3cr3t"
    auth = "SHA256 Credential=123456, Timestamp=1, Signature=deadbeef"
    errors = parse_graphql_errors(
        {
            "errors": [
                {
                    "message": f"error [10020]: {secret}; Authorization: {auth}",
                    "extensions": {"code": "10020"},
                }
            ]
        },
        secrets=(secret,),
    )

    assert len(errors) == 1
    assert errors[0].code == 10020
    assert secret not in errors[0].message
    assert auth not in errors[0].message
    assert "deadbeef" not in errors[0].message


def test_redaction_removes_secret_and_credential_shaped_values():
    secret = "top-secret-value"
    text = (
        f"secret={secret}; Authorization: SHA256 Credential=123, Timestamp=1, "
        "Signature=0123456789abcdef"
    )

    redacted = redact_secrets(text, secrets=(secret,))

    assert secret not in redacted
    assert "0123456789abcdef" not in redacted
    assert "Credential=123" not in redacted
    assert "[REDACTED]" in redacted


def test_signature_implementation_uses_sha256_bytes():
    payload = b'{"query":"{ ping }"}'
    expected = hashlib.sha256(
        b"123456" + b"7" + payload + b"unit-test-secret"
    ).hexdigest()
    assert calculate_signature("123456", 7, payload, "unit-test-secret") == expected
