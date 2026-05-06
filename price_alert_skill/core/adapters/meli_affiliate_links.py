"""Concrete adapter for Mercado Livre affiliate-link generation."""

from __future__ import annotations

from price_alert_skill import generate_melila_links as melila_impl


class MeliAffiliateLinkGenerator:
    """Generate meli.la links using the existing Playwright-backed implementation."""

    def __call__(self, urls: list[str]) -> dict[str, str]:
        return melila_impl.generate_links(urls)
