"""Pure ranking helpers for selecting the strongest commercial deals."""

from __future__ import annotations

from typing import Any

from .lane_rules import (
    get_authoritative_discount_pct,
    get_lane_rank,
    is_shopee_source_aware,
)


def deal_sort_key(deal: dict[str, Any]) -> tuple[Any, ...]:
    """Build a stable ranking key for deals inside the same lane.

    Shopee's reference savings may be reconstructed for display, but its
    provider percentage remains the authoritative ranking signal. Shopee deals
    are kept after deals with provider-known savings when mixed in one lane.
    This prevents an inference from changing cross-provider ranking.
    """
    price = float(deal.get("current_price") or 0.0)
    title = str(deal.get("title", "")).lower()

    if is_shopee_source_aware(deal):
        authoritative_discount = get_authoritative_discount_pct(deal)
        return (
            1,
            -(authoritative_discount or 0.0),
            price,
            title,
        )

    savings = -(float(deal.get("savings_brl") or 0.0))
    discount = -(float(deal.get("discount_pct") or 0.0))
    return (0, savings, discount, price, title)


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
