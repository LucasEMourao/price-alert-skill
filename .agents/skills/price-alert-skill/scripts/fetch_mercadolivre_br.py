#!/usr/bin/env python3
"""Compatibility wrapper for the repo-level price_alert_skill.fetch_mercadolivre_br module."""

from __future__ import annotations

from _package_bootstrap import bootstrap_package

bootstrap_package()

from price_alert_skill.fetch_mercadolivre_br import *  # noqa: F401,F403


if __name__ == "__main__":
    from price_alert_skill.fetch_mercadolivre_br import main

    raise SystemExit(main())
