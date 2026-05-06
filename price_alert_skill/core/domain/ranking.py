"""Pure ranking helpers for selecting the strongest commercial deals."""

from __future__ import annotations

from typing import Any

from .lane_rules import get_lane_rank


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
