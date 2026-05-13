#!/usr/bin/env python3

"""Configuration for affiliate link generation and marketplace settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

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

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "brunoentende-20")
WHATSAPP_GROUP = os.environ.get("WHATSAPP_GROUP", "")
WHATSAPP_GROUP_JID = os.environ.get("WHATSAPP_GROUP_JID", "")
WHATSAPP_SENDER_BACKEND = os.environ.get("WHATSAPP_SENDER_BACKEND", "playwright")
WHATSAPP_SEND_INTERVAL_SECONDS = os.environ.get("WHATSAPP_SEND_INTERVAL_SECONDS", "")
BAILEYS_GATEWAY_URL = os.environ.get("BAILEYS_GATEWAY_URL", "http://127.0.0.1:3015")
PRICE_ALERT_RUNTIME = os.environ.get("PRICE_ALERT_RUNTIME", "auto")
WHATSAPP_CHROME_PATH = os.environ.get("WHATSAPP_CHROME_PATH", "")
WHATSAPP_PROFILE_DIR = os.environ.get("WHATSAPP_PROFILE_DIR", "")

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
