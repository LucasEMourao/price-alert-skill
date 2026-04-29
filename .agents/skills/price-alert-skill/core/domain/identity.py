"""Pure identity helpers for product and offer tracking."""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_url_for_key(url: str) -> str:
    """Strip query string and fragment so the same product keeps a stable key."""
    parsed = urlparse(url or "")
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}".lower().strip("/")


def build_product_key(url: str) -> str:
    """Build a stable product key from the raw product URL."""
    normalized = normalize_url_for_key(url)
    return normalized or (url or "").strip().lower()


def build_offer_key(product_key: str, current_price: float | None) -> str:
    """Build an offer key that changes when the price changes."""
    if current_price is None:
        return product_key
    return f"{product_key}|{float(current_price):.2f}"


def calculate_savings_brl(
    current_price: float | None,
    previous_price: float | None,
) -> float:
    """Calculate absolute savings in BRL."""
    if current_price is None or previous_price is None:
        return 0.0
    if previous_price <= current_price:
        return 0.0
    return round(previous_price - current_price, 2)
