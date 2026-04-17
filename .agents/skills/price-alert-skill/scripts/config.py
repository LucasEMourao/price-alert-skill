#!/usr/bin/env python3

"""Configuration for affiliate link generation and marketplace settings.

Credentials are loaded from .env file (create from .env.example).
Never commit .env to version control.
"""

import os
from pathlib import Path

# Load .env file if it exists
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "brunoentende-20")
WHATSAPP_GROUP = os.environ.get("WHATSAPP_GROUP", "")

# ML Affiliate login credentials (loaded from .env)
ML_AFFILIATE_EMAIL = os.environ.get("ML_AFFILIATE_EMAIL", "")
ML_AFFILIATE_PASSWORD = os.environ.get("ML_AFFILIATE_PASSWORD", "")

# Optional proxy for Mercado Livre affiliate access
ML_PROXY = os.environ.get("ML_PROXY", "")


def resolve_whatsapp_group(cli_group: str = "") -> str:
    """Resolve the WhatsApp group name from CLI input or .env."""
    explicit_group = (cli_group or "").strip()
    if explicit_group:
        return explicit_group
    return WHATSAPP_GROUP.strip()
