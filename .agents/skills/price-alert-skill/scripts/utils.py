#!/usr/bin/env python3
"""Compatibility wrapper for the repo-level price_alert_skill.utils module."""

from __future__ import annotations

from _package_bootstrap import bootstrap_package

bootstrap_package()

from price_alert_skill.utils import *  # noqa: F401,F403
