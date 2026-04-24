#!/usr/bin/env python3

"""Selection rules and category ranking for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


CADENCE_CONFIG = {
    "scan_interval_minutes": 15,
    "batch_interval_minutes": 30,
    "normal_ttl_minutes": 90,
    "super_retry_ttl_minutes": 60,
    "same_offer_cooldown_hours": 24,
    "super_offer_cooldown_hours": 6,
    "min_discount_improvement_points": 5.0,
    "min_savings_improvement_brl": 50.0,
    "normal_max_retries": 2,
    "super_max_retries": 3,
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


CATEGORY_RULES = {
    "perifericos": {
        "band": "cheap",
        "min_discount_pct": 18.0,
        "min_savings_brl": 30.0,
        "max_items": 2,
        "super_discount_pct": 25.0,
        "super_savings_brl": 80.0,
        "sort_mode": "cheap",
    },
    "audio_comunicacao": {
        "band": "cheap",
        "min_discount_pct": 18.0,
        "min_savings_brl": 40.0,
        "max_items": 3,
        "super_discount_pct": 25.0,
        "super_savings_brl": 100.0,
        "sort_mode": "cheap",
    },
    "refrigeracao_leve": {
        "band": "cheap",
        "min_discount_pct": 18.0,
        "min_savings_brl": 30.0,
        "max_items": 2,
        "super_discount_pct": 25.0,
        "super_savings_brl": 80.0,
        "sort_mode": "cheap",
    },
    "armazenamento": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 40.0,
        "max_items": 3,
        "super_discount_pct": 20.0,
        "super_savings_brl": 120.0,
        "sort_mode": "mid",
    },
    "memoria": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 40.0,
        "max_items": 3,
        "super_discount_pct": 20.0,
        "super_savings_brl": 100.0,
        "sort_mode": "mid",
    },
    "fontes": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 50.0,
        "max_items": 2,
        "super_discount_pct": 20.0,
        "super_savings_brl": 120.0,
        "sort_mode": "mid",
    },
    "gabinetes": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 60.0,
        "max_items": 2,
        "super_discount_pct": 20.0,
        "super_savings_brl": 150.0,
        "sort_mode": "mid",
    },
    "refrigeracao_premium": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 60.0,
        "max_items": 2,
        "super_discount_pct": 20.0,
        "super_savings_brl": 150.0,
        "sort_mode": "mid",
    },
    "monitores": {
        "band": "mid",
        "min_discount_pct": 12.0,
        "min_savings_brl": 80.0,
        "max_items": 3,
        "super_discount_pct": 20.0,
        "super_savings_brl": 150.0,
        "sort_mode": "mid",
    },
    "processadores": {
        "band": "expensive",
        "min_discount_pct": 9.0,
        "min_savings_brl": 120.0,
        "max_items": 3,
        "super_discount_pct": 15.0,
        "super_savings_brl": 200.0,
        "sort_mode": "expensive",
    },
    "placas_mae": {
        "band": "expensive",
        "min_discount_pct": 9.0,
        "min_savings_brl": 120.0,
        "max_items": 3,
        "super_discount_pct": 15.0,
        "super_savings_brl": 200.0,
        "sort_mode": "expensive",
    },
    "placas_video": {
        "band": "expensive",
        "min_discount_pct": 9.0,
        "min_savings_brl": 150.0,
        "max_items": 4,
        "super_discount_pct": 15.0,
        "super_savings_brl": 300.0,
        "sort_mode": "expensive",
    },
    "notebooks_gamer": {
        "band": "expensive",
        "min_discount_pct": 9.0,
        "min_savings_brl": 200.0,
        "max_items": 3,
        "super_discount_pct": 15.0,
        "super_savings_brl": 400.0,
        "sort_mode": "expensive",
    },
    "pc_gamer": {
        "band": "expensive",
        "min_discount_pct": 9.0,
        "min_savings_brl": 250.0,
        "max_items": 2,
        "super_discount_pct": 15.0,
        "super_savings_brl": 400.0,
        "sort_mode": "expensive",
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

    quality_passed = passes_quality_filters(prepared)
    prepared["quality_passed"] = quality_passed
    prepared["is_super_promo"] = is_super_promo(prepared)
    return prepared


def get_category_rule(category: str) -> dict[str, Any]:
    """Return the category rule or a conservative default rule."""
    return CATEGORY_RULES.get(category, CATEGORY_RULES[DEFAULT_CATEGORY])


def qualifies_normal(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> bool:
    """Return True when a deal passes the standard category thresholds."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    return (
        bool(deal.get("quality_passed", True))
        and float(deal.get("discount_pct") or 0.0) >= float(rule["min_discount_pct"])
        and float(deal.get("savings_brl") or 0.0) >= float(rule["min_savings_brl"])
    )


def is_super_promo(deal: dict[str, Any], rule: dict[str, Any] | None = None) -> bool:
    """Return True when a deal crosses the super-promo threshold."""
    rule = rule or get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    if not deal.get("quality_passed", True):
        return False
    return (
        float(deal.get("discount_pct") or 0.0) >= float(rule["super_discount_pct"])
        or float(deal.get("savings_brl") or 0.0) >= float(rule["super_savings_brl"])
    )


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


def deal_sort_key(deal: dict[str, Any]) -> tuple[Any, ...]:
    """Build a stable ranking key for a deal inside its category."""
    rule = get_category_rule(deal.get("category", DEFAULT_CATEGORY))
    sort_mode = rule["sort_mode"]
    is_super = 0 if deal.get("is_super_promo") else 1
    discount = -(float(deal.get("discount_pct") or 0.0))
    savings = -(float(deal.get("savings_brl") or 0.0))
    price = float(deal.get("current_price") or 0.0)
    title = str(deal.get("title", "")).lower()

    if sort_mode == "cheap":
        return (is_super, discount, savings, price, title)

    return (is_super, savings, discount, price, title)


def sort_deals_for_category(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort deals according to the category ranking rules."""
    return sorted(deals, key=deal_sort_key)


def is_better_deal(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """Return True when candidate outranks current according to the category rules."""
    return deal_sort_key(candidate) < deal_sort_key(current)


def round_robin_select(grouped_deals: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Select deals in rounds to preserve category variety."""
    ordered_groups = {
        category: sort_deals_for_category(deals)
        for category, deals in grouped_deals.items()
        if deals
    }
    selected: list[dict[str, Any]] = []
    round_index = 0

    while ordered_groups:
        took_any = False
        for category in list(ordered_groups.keys()):
            rule = get_category_rule(category)
            if round_index >= int(rule["max_items"]):
                ordered_groups.pop(category, None)
                continue

            deals = ordered_groups[category]
            if round_index < len(deals):
                selected.append(deals[round_index])
                took_any = True
            else:
                ordered_groups.pop(category, None)

        if not took_any:
            break
        round_index += 1

    return selected
