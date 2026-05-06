#!/usr/bin/env python3

"""Selection rules and lane ranking for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any

from price_alert_skill.core.domain.identity import (
    build_offer_key,
    build_product_key,
    calculate_savings_brl,
    normalize_url_for_key,
)
from price_alert_skill.core.domain.lane_rules import (
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
from price_alert_skill.core.domain.ranking import (
    deal_sort_key,
    is_better_deal,
    sort_deals_for_sending,
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
