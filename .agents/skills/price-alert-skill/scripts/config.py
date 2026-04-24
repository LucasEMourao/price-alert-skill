#!/usr/bin/env python3

"""Configuration for affiliate link generation and marketplace settings.

Credentials are loaded from .env file (create from .env.example).
Never commit .env to version control.
"""

import os
import sys
from pathlib import Path

# Load .env file if it exists
_env_file = Path(__file__).resolve().parent.parent / ".env"
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


def resolve_whatsapp_group(cli_group: str = "") -> str:
    """Resolve the WhatsApp group name from CLI input or .env."""
    explicit_group = (cli_group or "").strip()
    if explicit_group:
        return explicit_group
    return WHATSAPP_GROUP.strip()


def resolve_whatsapp_chrome_path() -> str:
    """Resolve the Chrome executable path for WhatsApp Web automation."""
    explicit_path = WHATSAPP_CHROME_PATH.strip()
    if explicit_path and Path(explicit_path).exists():
        return explicit_path

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

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return str(
                Path(local_app_data)
                / "price-alert-skill"
                / "whatsapp_chrome_profile"
            )

    return str(
        Path(__file__).resolve().parent.parent
        / "data"
        / "whatsapp_session"
        / "chrome_profile"
    )
