#!/usr/bin/env python3

"""Selection rules and lane ranking for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from core.domain.lane_rules import (
    ACTIVE_LANES,
    CATEGORY_RULES,
    DEFAULT_CATEGORY,
    LANE_PRIORITY,
    classify_deal_lane,
    get_category_rule,
    get_lane_rank,
    passes_quality_filters,
    qualifies_normal,
    qualifies_priority,
    qualifies_urgent,
)


CADENCE_CONFIG = {
    "scan_interval_minutes": 15,
    "urgent_window_minutes": 45,
    "urgent_window_scans": 3,
    "priority_window_minutes": 90,
    "priority_window_scans": 6,
    "normal_window_minutes": 180,
    "normal_window_scans": 12,
    "sender_poll_seconds": 20,
    "sender_idle_exit_seconds": 300,
    "same_offer_cooldown_hours": 24,
    "urgent_offer_cooldown_hours": 6,
    "min_discount_improvement_points": 5.0,
    "min_savings_improvement_brl": 50.0,
    "max_send_retries": 2,
    "retry_backoff_seconds": 180,
    "non_urgent_lane_sequence": ("priority", "priority", "priority", "normal"),
}


QUERY_DEFINITIONS = [
    {"query": "mouse gamer", "category": "perifericos"},
    {"query": "teclado mecanico gamer", "category": "perifericos"},
    {"query": "mousepad gamer", "category": "perifericos"},
    {"query": "headset gamer", "category": "audio_comunicacao"},
    {"query": "webcam full hd", "category": "audio_comunicacao"},
    {"query": "microfone usb", "category": "audio_comunicacao"},
    {"query": "air cooler", "category": "refrigeracao_leve"},
    {"query": "ssd nvme 1tb", "category": "armazenamento"},
    {"query": "ssd nvme 2tb", "category": "armazenamento"},
    {"query": "ssd sata 1tb", "category": "armazenamento"},
    {"query": "ssd 2tb", "category": "armazenamento"},
    {"query": "memoria ram ddr4", "category": "memoria"},
    {"query": "memoria ram ddr5", "category": "memoria"},
    {"query": "fonte 650w", "category": "fontes"},
    {"query": "fonte 750w", "category": "fontes"},
    {"query": "gabinete gamer", "category": "gabinetes"},
    {"query": "water cooler", "category": "refrigeracao_premium"},
    {"query": "monitor gamer", "category": "monitores"},
    {"query": "processador ryzen", "category": "processadores"},
    {"query": "processador intel core", "category": "processadores"},
    {"query": "placa mae am5", "category": "placas_mae"},
    {"query": "placa mae lga1700", "category": "placas_mae"},
    {"query": "placa de video rtx", "category": "placas_video"},
    {"query": "placa de video rx", "category": "placas_video"},
    {"query": "notebook gamer", "category": "notebooks_gamer"},
    {"query": "pc gamer", "category": "pc_gamer"},
    {"query": "computador gamer", "category": "pc_gamer"},
    {"query": "desktop gamer", "category": "pc_gamer"},
]


QUERY_TO_CATEGORY = {
    definition["query"]: definition["category"] for definition in QUERY_DEFINITIONS
}

ALL_QUERIES = [definition["query"] for definition in QUERY_DEFINITIONS]


def get_queries() -> list[str]:
    """Return the cadence query list in the configured order."""
    return list(ALL_QUERIES)


def get_query_category(query: str) -> str:
    """Resolve the category for a scan query."""
    return QUERY_TO_CATEGORY.get((query or "").strip().lower(), DEFAULT_CATEGORY)


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


def prepare_deal_for_selection(deal: dict[str, Any]) -> dict[str, Any]:
    """Add selection metadata to a scanned deal."""
    prepared = dict(deal)
    source_query = prepared.get("source_query") or prepared.get("query", "")
    category = prepared.get("category") or get_query_category(source_query)
    product_url = prepared.get("product_url") or prepared.get("url", "")
    current_price = prepared.get("current_price")
    previous_price = prepared.get("previous_price")

    prepared["source_query"] = source_query
    prepared["category"] = category
    prepared["product_url"] = product_url
    prepared["product_key"] = prepared.get("product_key") or build_product_key(product_url)
    prepared["offer_key"] = prepared.get("offer_key") or build_offer_key(
        prepared["product_key"],
        current_price,
    )
    prepared["savings_brl"] = prepared.get("savings_brl")
    if prepared["savings_brl"] is None:
        prepared["savings_brl"] = calculate_savings_brl(current_price, previous_price)

    prepared["quality_passed"] = passes_quality_filters(prepared)
    prepared["lane"] = classify_deal_lane(prepared)
    prepared["is_super_promo"] = prepared["lane"] == "urgent"
    return prepared


def deal_sort_key(deal: dict[str, Any]) -> tuple[Any, ...]:
    """Build a stable ranking key for deals inside the same lane."""
    savings = -(float(deal.get("savings_brl") or 0.0))
    discount = -(float(deal.get("discount_pct") or 0.0))
    price = float(deal.get("current_price") or 0.0)
    title = str(deal.get("title", "")).lower()
    return (savings, discount, price, title)


def sort_deals_for_sending(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort deals by commercial strength for sender consumption."""
    return sorted(deals, key=deal_sort_key)


def is_better_deal(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """Return True when candidate should replace current in the pools."""
    candidate_rank = get_lane_rank(candidate.get("lane", "discarded"))
    current_rank = get_lane_rank(current.get("lane", "discarded"))
    if candidate_rank != current_rank:
        return candidate_rank > current_rank
    return deal_sort_key(candidate) < deal_sort_key(current)
