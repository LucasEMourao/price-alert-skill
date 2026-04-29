"""Concrete Mercado Livre marketplace runner adapter."""

from __future__ import annotations

import fetch_ml_browser as mercadolivre_impl


class MercadoLivreMarketplaceScanner:
    """Run Mercado Livre searches through the existing Playwright implementation."""

    def __call__(self, *, query: str, max_results: int) -> dict:
        return mercadolivre_impl.run(query=query, max_results=max_results)
