#!/usr/bin/env python3

"""Configuration for affiliate link generation and marketplace settings."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core.domain.brand_filter import parse_configured_brand_names
from .paths import REPO_ROOT, resolve_skill_root
from .runtime import (
    RuntimeEnvironment,
    find_linux_browser_executable,
    resolve_runtime_environment,
)


_skill_root = resolve_skill_root()

# Load .env file from the active skill home if it exists.
_env_file = _skill_root / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)


def _parse_env_bool(value: str, *, default: bool = False) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def _parse_positive_float(value: str, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_positive_int(value: str, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_marketplace_list(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated marketplace list in stable order."""
    if value is None:
        return ()

    marketplaces: list[str] = []
    for raw_marketplace in value.split(","):
        marketplace = raw_marketplace.strip().lower()
        if marketplace and marketplace not in marketplaces:
            marketplaces.append(marketplace)
    return tuple(marketplaces)


@dataclass(frozen=True)
class ShopeeSettings:
    """Opt-in Shopee transport settings.

    ``SHOPEE_ENABLED`` is the hard gate: listing ``shopee_br`` in
    ``PRICE_ALERT_MARKETPLACES`` cannot enable the provider by itself.  The
    marketplace list is an additional activation gate used by later workflow
    integration.  Credentials are read only while the hard gate is enabled.
    """

    enabled: bool
    app_id: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    api_url: str = "https://open-api.affiliate.shopee.com.br/graphql"
    timeout_seconds: float = 30.0
    max_pages_per_query: int = 5


def resolve_shopee_settings() -> ShopeeSettings:
    """Resolve Shopee settings without loading disabled-provider credentials."""
    enabled = _parse_env_bool(os.environ.get("SHOPEE_ENABLED", "0"))
    return ShopeeSettings(
        enabled=enabled,
        app_id=os.environ.get("SHOPEE_APP_ID", "").strip() if enabled else "",
        app_secret=os.environ.get("SHOPEE_APP_SECRET", "") if enabled else "",
        api_url=os.environ.get(
            "SHOPEE_API_URL",
            "https://open-api.affiliate.shopee.com.br/graphql",
        ).strip(),
        timeout_seconds=_parse_positive_float(
            os.environ.get("SHOPEE_REQUEST_TIMEOUT_SECONDS", "30"),
            default=30.0,
        ),
        max_pages_per_query=_parse_positive_int(
            os.environ.get("SHOPEE_MAX_PAGES_PER_QUERY", "5"),
            default=5,
        ),
    )


SHOPEE_SETTINGS = resolve_shopee_settings()
SHOPEE_ENABLED = SHOPEE_SETTINGS.enabled
SHOPEE_APP_ID = SHOPEE_SETTINGS.app_id
SHOPEE_APP_SECRET = SHOPEE_SETTINGS.app_secret
SHOPEE_API_URL = SHOPEE_SETTINGS.api_url
SHOPEE_REQUEST_TIMEOUT_SECONDS = SHOPEE_SETTINGS.timeout_seconds
SHOPEE_MAX_PAGES_PER_QUERY = SHOPEE_SETTINGS.max_pages_per_query
PRICE_ALERT_MARKETPLACES = os.environ.get(
    "PRICE_ALERT_MARKETPLACES",
    "amazon_br,mercadolivre_br",
).strip()
PRICE_ALERT_SEND_MARKETPLACES = os.environ.get(
    "PRICE_ALERT_SEND_MARKETPLACES",
    "",
).strip()


def resolve_price_alert_marketplaces() -> tuple[str, ...]:
    """Resolve the scanner allowlist, preserving the legacy default.

    ``PRICE_ALERT_MARKETPLACES`` controls which providers are scanned.  Shopee
    has an additional hard gate: it is ignored by the Shopee client unless
    ``SHOPEE_ENABLED=1``.  Removing ``shopee_br`` from this list is therefore
    the scan rollback switch and does not touch persisted queue state.
    """
    configured = os.environ.get("PRICE_ALERT_MARKETPLACES", PRICE_ALERT_MARKETPLACES)
    return _parse_marketplace_list(configured)


def resolve_price_alert_send_marketplaces() -> tuple[str, ...] | None:
    """Resolve the optional sender allowlist.

    An empty ``PRICE_ALERT_SEND_MARKETPLACES`` means no additional sender
    filter, which preserves delivery of existing marketplace entries.  A
    non-empty list can be used as an independent rollback control for queued
    Shopee deals.
    """
    configured = os.environ.get(
        "PRICE_ALERT_SEND_MARKETPLACES",
        PRICE_ALERT_SEND_MARKETPLACES,
    )
    marketplaces = _parse_marketplace_list(configured)
    return marketplaces or None


AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "brunoentende-20")
WHATSAPP_GROUP = os.environ.get("WHATSAPP_GROUP", "")
WHATSAPP_GROUP_JID = os.environ.get("WHATSAPP_GROUP_JID", "")
WHATSAPP_SENDER_BACKEND = os.environ.get("WHATSAPP_SENDER_BACKEND", "playwright")
WHATSAPP_SEND_INTERVAL_SECONDS = os.environ.get("WHATSAPP_SEND_INTERVAL_SECONDS", "")
BAILEYS_GATEWAY_URL = os.environ.get("BAILEYS_GATEWAY_URL", "http://127.0.0.1:3015")
PRICE_ALERT_RUNTIME = os.environ.get("PRICE_ALERT_RUNTIME", "auto")
WHATSAPP_CHROME_PATH = os.environ.get("WHATSAPP_CHROME_PATH", "")
WHATSAPP_PROFILE_DIR = os.environ.get("WHATSAPP_PROFILE_DIR", "")
PRICE_ALERT_ALLOWED_BEAUTY_BRANDS = os.environ.get("PRICE_ALERT_ALLOWED_BEAUTY_BRANDS", "")

# ML Affiliate login credentials (loaded from .env)
ML_AFFILIATE_EMAIL = os.environ.get("ML_AFFILIATE_EMAIL", "")
ML_AFFILIATE_PASSWORD = os.environ.get("ML_AFFILIATE_PASSWORD", "")

# Optional proxy for Mercado Livre affiliate access
ML_PROXY = os.environ.get("ML_PROXY", "")


def configure_utf8_stdio() -> None:
    """Force UTF-8 stdio when the host console defaults to a legacy encoding."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def resolve_whatsapp_sender_backend() -> str:
    """Resolve the active WhatsApp sender backend."""
    backend = (WHATSAPP_SENDER_BACKEND or "playwright").strip().lower()
    if backend not in {"playwright", "baileys"}:
        raise ValueError("WHATSAPP_SENDER_BACKEND must be one of: playwright, baileys")
    return backend


def resolve_whatsapp_send_interval_seconds(backend: str | None = None) -> float:
    """Resolve the pause between consecutive WhatsApp sends."""
    raw_value = WHATSAPP_SEND_INTERVAL_SECONDS.strip()
    if raw_value:
        try:
            interval_seconds = float(raw_value)
        except ValueError as exc:
            raise ValueError("WHATSAPP_SEND_INTERVAL_SECONDS must be a number") from exc
        if interval_seconds < 0:
            raise ValueError("WHATSAPP_SEND_INTERVAL_SECONDS must be zero or greater")
        return interval_seconds

    resolved_backend = (backend or resolve_whatsapp_sender_backend()).strip().lower()
    if resolved_backend == "baileys":
        return 30.0
    return 0.0


def resolve_whatsapp_group_jid() -> str:
    """Resolve the stable WhatsApp group JID used by the Baileys backend."""
    return WHATSAPP_GROUP_JID.strip()


def resolve_baileys_gateway_url() -> str:
    """Resolve the local Baileys gateway base URL."""
    return (BAILEYS_GATEWAY_URL or "http://127.0.0.1:3015").strip().rstrip("/")


def resolve_whatsapp_group(cli_group: str = "") -> str:
    """Resolve the WhatsApp group name from CLI input or .env."""
    explicit_group = (cli_group or "").strip()
    if explicit_group:
        return explicit_group
    configured_group = WHATSAPP_GROUP.strip()
    if configured_group:
        return configured_group
    if resolve_whatsapp_sender_backend() == "baileys":
        return resolve_whatsapp_group_jid()
    return ""


def resolve_allowed_beauty_brand_names() -> tuple[str, ...] | None:
    """Resolve the optional runtime override for the beauty brand allowlist."""
    return parse_configured_brand_names(
        os.environ.get(
            "PRICE_ALERT_ALLOWED_BEAUTY_BRANDS",
            PRICE_ALERT_ALLOWED_BEAUTY_BRANDS,
        )
    )


def resolve_price_alert_runtime() -> RuntimeEnvironment:
    """Resolve the runtime used for host-specific adapters."""
    return resolve_runtime_environment(PRICE_ALERT_RUNTIME)


def resolve_whatsapp_chrome_path() -> str:
    """Resolve the Chrome executable path for WhatsApp Web automation."""
    explicit_path = WHATSAPP_CHROME_PATH.strip()
    if explicit_path:
        return explicit_path

    runtime = resolve_price_alert_runtime()
    if runtime.is_linux:
        return find_linux_browser_executable()

    candidate_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidate_paths.append(
            Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe"
        )

    for candidate in candidate_paths:
        if candidate.exists():
            return str(candidate)

    return ""


def resolve_whatsapp_profile_dir() -> str:
    """Resolve the persistent Chrome profile directory for WhatsApp Web."""
    explicit_path = WHATSAPP_PROFILE_DIR.strip()
    if explicit_path:
        return explicit_path

    runtime = resolve_price_alert_runtime()
    if runtime.is_windows:
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return str(
                Path(local_app_data)
                / "price-alert-skill"
                / "whatsapp_chrome_profile"
            )
        return str(
            resolve_skill_root()
            / "data"
            / "whatsapp_session"
            / "windows_chrome_profile"
        )

    session_root = resolve_skill_root() / "data" / "whatsapp_session"
    legacy_linux_profile = session_root / "chrome_profile"
    if legacy_linux_profile.exists():
        return str(legacy_linux_profile)

    return str(session_root / "linux_chrome_profile")
