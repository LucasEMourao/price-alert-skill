"""Bootstrap helper for thin skill wrappers.

This file keeps the skill scripts focused on importing and invoking the
repo-level ``price_alert_skill`` package.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def bootstrap_package() -> Path:
    """Expose the repo package and register the active skill home."""
    scripts_dir = Path(__file__).resolve().parent
    skill_root = scripts_dir.parent
    repo_root = skill_root.parents[2]

    os.environ.setdefault("PRICE_ALERT_SKILL_HOME", str(skill_root))
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root
