"""Path helpers shared by the repo package and the legacy skill wrappers."""

from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DEFAULT_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "price-alert-skill"


def resolve_skill_root() -> Path:
    """Resolve the active skill home used for .env, data and logs."""
    explicit = os.environ.get("PRICE_ALERT_SKILL_HOME", "").strip()
    if explicit:
        return Path(explicit).resolve()
    return DEFAULT_SKILL_ROOT.resolve()


def resolve_data_dir() -> Path:
    """Return the skill data directory."""
    return resolve_skill_root() / "data"


def resolve_logs_dir() -> Path:
    """Return the skill logs directory."""
    return resolve_skill_root() / "logs"
