"""Concrete Amazon marketplace runner adapter."""

from __future__ import annotations

import fetch_amazon_br as amazon_impl


class AmazonMarketplaceScanner:
    """Run Amazon marketplace searches through the existing implementation."""

    def __call__(self, *, query: str, max_results: int) -> dict:
        return amazon_impl.run(query=query, max_results=max_results)
