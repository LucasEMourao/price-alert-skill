#!/usr/bin/env python3
"""Compatibility wrapper for the repo-level price_alert_skill.config module."""

from __future__ import annotations

from _package_bootstrap import bootstrap_package

bootstrap_package()

from price_alert_skill.config import *  # noqa: F401,F403
