"""Pure identity helpers for product and offer tracking."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

BEAUTY_VARIANT_FAMILY_CATEGORIES = {"beleza_maquiagem"}
_VARIANT_CODE_PATTERN = re.compile(r"^[a-z]{1,2}\d{3,4}[a-z]?$")
_VARIANT_VALUE_PATTERN = re.compile(r"^[a-z]?\d{1,4}[a-z]?$")


def normalize_url_for_key(url: str) -> str:
    """Strip query string and fragment so the same product keeps a stable key."""
    parsed = urlparse(url or "")
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}".lower().strip("/")


def build_product_key(url: str) -> str:
    """Build a stable product key from the raw product URL."""
    normalized = normalize_url_for_key(url)
    return normalized or (url or "").strip().lower()


def normalize_title_for_key(title: str) -> str:
    """Normalize a title into a lowercase ASCII token stream."""
    ascii_title = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", " ", ascii_title.lower())
    return " ".join(normalized.split())


def build_variant_family_key(
    *,
    title: str,
    marketplace: str,
    category: str,
) -> str | None:
    """Collapse beauty makeup shade variants into one family key when safe."""
    normalized_category = (category or "").strip().lower()
    if normalized_category not in BEAUTY_VARIANT_FAMILY_CATEGORIES:
        return None

    tokens = normalize_title_for_key(title).split()
    if not tokens:
        return None

    family_tokens: list[str] = []
    variant_detected = False
    skip_next = False

    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue

        if _VARIANT_CODE_PATTERN.match(token):
            variant_detected = True
            continue

        if token in {"cor", "tom", "tone", "shade", "color"} and (index + 1) < len(tokens):
            next_token = tokens[index + 1]
            if _VARIANT_VALUE_PATTERN.match(next_token):
                variant_detected = True
                skip_next = True
                continue

        family_tokens.append(token)

    if not variant_detected:
        return None

    normalized_title = " ".join(family_tokens).strip()
    if not normalized_title:
        return None

    normalized_marketplace = (marketplace or "").strip().lower()
    return f"{normalized_marketplace}|{normalized_category}|{normalized_title}"


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
