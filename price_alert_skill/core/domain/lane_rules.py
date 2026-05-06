"""Pure lane classification rules for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any

from .types import ACTIVE_LANES


LANE_PRIORITY = {
    "discarded": 0,
    "normal": 1,
    "priority": 2,
    "urgent": 3,
}


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


DEFAULT_CATEGORY = "perifericos"

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


def get_category_rule(category: str) -> dict[str, Any]:
    """Return the category rule or a conservative default rule."""
    return CATEGORY_RULES.get(category, CATEGORY_RULES[DEFAULT_CATEGORY])


def get_lane_rank(lane: str) -> int:
    """Return the numeric ordering for a delivery lane."""
    return LANE_PRIORITY.get(lane, 0)


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
