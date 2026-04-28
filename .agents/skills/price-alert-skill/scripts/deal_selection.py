#!/usr/bin/env python3

"""Selection rules and lane ranking for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


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

LANE_PRIORITY = {
    "discarded": 0,
    "normal": 1,
    "priority": 2,
    "urgent": 3,
}

ACTIVE_LANES = ("urgent", "priority", "normal")


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


CATEGORY_RULES = {
    "perifericos": {
        "normal": {"discount_pct": 25.0, "savings_brl": 50.0},
        "priority": {"discount_pct": 40.0, "savings_brl": 120.0},
        "urgent": None,
    },
    "audio_comunicacao": {
        "normal": {"discount_pct": 22.0, "savings_brl": 50.0},
        "priority": {"discount_pct": 38.0, "savings_brl": 120.0},
        "urgent": None,
    },
    "refrigeracao_leve": {
        "normal": {"discount_pct": 20.0, "savings_brl": 40.0},
        "priority": {"discount_pct": 30.0, "savings_brl": 70.0},
        "urgent": None,
    },
    "armazenamento": {
        "normal": {"discount_pct": 12.0, "savings_brl": 60.0},
        "priority": {"discount_pct": 25.0, "savings_brl": 300.0},
        "urgent": None,
    },
    "memoria": {
        "normal": {"discount_pct": 15.0, "savings_brl": 60.0},
        "priority": {"discount_pct": 25.0, "savings_brl": 180.0},
        "urgent": None,
    },
    "fontes": {
        "normal": {"discount_pct": 15.0, "savings_brl": 70.0},
        "priority": {"discount_pct": 30.0, "savings_brl": 250.0},
        "urgent": None,
    },
    "gabinetes": {
        "normal": {"discount_pct": 15.0, "savings_brl": 80.0},
        "priority": {"discount_pct": 35.0, "savings_brl": 220.0},
        "urgent": None,
    },
    "refrigeracao_premium": {
        "normal": {"discount_pct": 15.0, "savings_brl": 80.0},
        "priority": {"discount_pct": 30.0, "savings_brl": 180.0},
        "urgent": None,
    },
    "pc_gamer": {
        "normal": {"discount_pct": 12.0, "savings_brl": 400.0},
        "priority": {"discount_pct": 22.0, "savings_brl": 800.0},
        "urgent": None,
    },
    "monitores": {
        "normal": {"discount_pct": 12.0, "savings_brl": 80.0},
        "priority": {"discount_pct": 30.0, "savings_brl": 350.0},
        "urgent": {"discount_pct": 40.0, "savings_brl": 700.0},
    },
    "processadores": {
        "normal": {"discount_pct": 9.0, "savings_brl": 120.0},
        "priority": {"discount_pct": 25.0, "savings_brl": 450.0},
        "urgent": {"discount_pct": 38.0, "savings_brl": 700.0},
    },
    "placas_mae": {
        "normal": {"discount_pct": 9.0, "savings_brl": 120.0},
        "priority": {"discount_pct": 30.0, "savings_brl": 700.0},
        "urgent": {"discount_pct": 42.0, "savings_brl": 1300.0},
    },
    "placas_video": {
        "normal": {"discount_pct": 9.0, "savings_brl": 150.0},
        "priority": {"discount_pct": 25.0, "savings_brl": 700.0},
        "urgent": {"discount_pct": 40.0, "savings_brl": 1200.0},
    },
    "notebooks_gamer": {
        "normal": {"discount_pct": 9.0, "savings_brl": 200.0},
        "priority": {"discount_pct": 22.0, "savings_brl": 1200.0},
        "urgent": {"discount_pct": 30.0, "savings_brl": 2000.0},
    },
}


QUERY_TO_CATEGORY = {
    definition["query"]: definition["category"] for definition in QUERY_DEFINITIONS
}

DEFAULT_CATEGORY = "perifericos"
ALL_QUERIES = [definition["query"] for definition in QUERY_DEFINITIONS]

_PC_GAMER_GROUPS = {
    "cpu": ("ryzen", "intel core", "i5", "i7", "i9"),
    "gpu": ("rtx", "rx"),
    "memory": ("16gb", "32gb"),
    "storage": ("ssd", "nvme"),
}
_GPU_ACCESSORY_MARKERS = ("suporte", "cabo", "water block", "fan kit")
_PROCESSOR_MODEL_MARKERS = (
    "ryzen 3",
    "ryzen 5",
    "ryzen 7",
    "ryzen 9",
    "intel core i3",
    "intel core i5",
    "intel core i7",
    "intel core i9",
)
_NOTEBOOK_SPEC_MARKERS = (
    "rtx",
    "rx",
    "ryzen",
    "intel core",
    "i5",
    "i7",
    "i9",
)


def get_queries() -> list[str]:
    """Return the cadence query list in the configured order."""
    return list(ALL_QUERIES)


def get_query_category(query: str) -> str:
    """Resolve the category for a scan query."""
    return QUERY_TO_CATEGORY.get((query or "").strip().lower(), DEFAULT_CATEGORY)


def get_category_rule(category: str) -> dict[str, Any]:
    """Return the category rule or a conservative default rule."""
    return CATEGORY_RULES.get(category, CATEGORY_RULES[DEFAULT_CATEGORY])


def get_lane_rank(lane: str) -> int:
    """Return the numeric ordering for a delivery lane."""
    return LANE_PRIORITY.get(lane, 0)


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


def passes_quality_filters(deal: dict[str, Any]) -> bool:
    """Apply extra quality gates for expensive/noisy categories."""
    category = deal.get("category", "")
    title = str(deal.get("title", "")).lower()

    if category == "pc_gamer":
        matched_groups = 0
        for keywords in _PC_GAMER_GROUPS.values():
            if any(keyword in title for keyword in keywords):
                matched_groups += 1
        return matched_groups >= 2

    if category == "placas_video":
        return not any(marker in title for marker in _GPU_ACCESSORY_MARKERS)

    if category == "processadores":
        return any(marker in title for marker in _PROCESSOR_MODEL_MARKERS)

    if category == "notebooks_gamer":
        return any(marker in title for marker in _NOTEBOOK_SPEC_MARKERS)

    return True


def _meets_normal_threshold(deal: dict[str, Any], rule: dict[str, Any]) -> bool:
    threshold = rule["normal"]
    return (
        float(deal.get("discount_pct") or 0.0) >= float(threshold["discount_pct"])
        and float(deal.get("savings_brl") or 0.0) >= float(threshold["savings_brl"])
    )


def _meets_either_threshold(
    deal: dict[str, Any],
    threshold: dict[str, Any] | None,
) -> bool:
    if not threshold:
        return False
    return (
        float(deal.get("discount_pct") or 0.0) >= float(threshold["discount_pct"])
        or float(deal.get("savings_brl") or 0.0) >= float(threshold["savings_brl"])
    )


def qualifies_normal(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> bool:
    """Return True when a deal passes the standard category thresholds."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    return bool(deal.get("quality_passed", True)) and _meets_normal_threshold(deal, rule)


def qualifies_priority(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> bool:
    """Return True when a deal qualifies for the priority lane."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    return bool(deal.get("quality_passed", True)) and _meets_either_threshold(
        deal,
        rule["priority"],
    )


def qualifies_urgent(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> bool:
    """Return True when a deal qualifies for the urgent lane."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    return bool(deal.get("quality_passed", True)) and _meets_either_threshold(
        deal,
        rule.get("urgent"),
    )


def classify_deal_lane(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> str:
    """Classify a deal into urgent, priority, normal, or discarded."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))

    if not deal.get("quality_passed", True):
        return "discarded"
    if qualifies_urgent(deal, rule):
        return "urgent"
    if qualifies_priority(deal, rule):
        return "priority"
    if qualifies_normal(deal, rule):
        return "normal"
    return "discarded"


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
