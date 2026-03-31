#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any

from report_price_history import load_report

ROOT = Path(__file__).resolve().parents[1]
MIN_RELEVANT_DISCOUNT_PCT = 1.0


def brl(value: float | None) -> str | None:
    if value is None:
        return None
    whole, frac = f"{value:.2f}".split(".")
    parts = []
    while whole:
        parts.append(whole[-3:])
        whole = whole[:-3]
    return f"R$ {'.'.join(reversed(parts))},{frac}"


def urgency_level(item: dict[str, Any]) -> str:
    discount = item.get("discount_from_previous_pct")
    if discount is None:
        return "info"
    if discount >= 15:
        return "high"
    if discount > 0:
        return "medium"
    return "low"


def price_reference(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("previous_price") is not None:
        return {
            "kind": "previous_snapshot",
            "value": item["previous_price"],
            "text": brl(item["previous_price"]),
            "captured_at": item.get("previous_captured_at"),
        }
    if item.get("zoom_median_price") is not None:
        return {
            "kind": "zoom_median_price",
            "value": item["zoom_median_price"],
            "text": brl(item["zoom_median_price"]),
            "captured_at": None,
        }
    if item.get("zoom_current_best_price") is not None:
        return {
            "kind": "zoom_best_offer",
            "value": item["zoom_current_best_price"],
            "text": brl(item["zoom_current_best_price"]),
            "captured_at": None,
        }
    return {
        "kind": "unavailable",
        "value": None,
        "text": None,
        "captured_at": None,
    }


def build_payload(item: dict[str, Any], min_relevant_discount_pct: float) -> dict[str, Any]:
    previous = price_reference(item)
    discount_pct = item.get("discount_from_previous_pct")
    if discount_pct is None and previous["value"] and item.get("current_price") is not None and previous["value"] != 0:
        discount_pct = round(((previous["value"] - item["current_price"]) / previous["value"]) * 100, 2)

    reason = None
    actionable = False
    if discount_pct is not None and discount_pct >= min_relevant_discount_pct:
        if previous.get("kind") == "zoom_median_price":
            reason = "below_zoom_median"
        elif item.get("is_at_lowest_price"):
            reason = "new_lowest_price"
        else:
            reason = "price_drop"
        actionable = True

    return {
        "product_id": item["product_id"],
        "marketplace": item["marketplace"],
        "query": item["query"],
        "product_title": item["title"],
        "product_url": item["url"],
        "current_price": item.get("current_price"),
        "current_price_text": brl(item.get("current_price")),
        "previous_price_reference": previous,
        "discount_pct": discount_pct,
        "urgency_level": urgency_level({**item, "discount_from_previous_pct": discount_pct}),
        "reason": reason,
        "actionable": actionable,
        "lowest_recorded_price": item.get("lowest_recorded_price"),
        "lowest_recorded_price_text": brl(item.get("lowest_recorded_price")),
        "highest_recorded_price": item.get("highest_recorded_price"),
        "highest_recorded_price_text": brl(item.get("highest_recorded_price")),
        "priced_snapshots": item.get("priced_snapshots"),
        "is_at_lowest_price": item.get("is_at_lowest_price"),
        "zoom_baseline": {
            "median_price": item.get("zoom_median_price"),
            "median_price_text": brl(item.get("zoom_median_price")),
            "current_best_price": item.get("zoom_current_best_price"),
            "current_best_price_text": brl(item.get("zoom_current_best_price")),
            "offer_count": item.get("zoom_offer_count"),
            "tip_text": item.get("zoom_tip_text"),
        },
        "render_constraints": {
            "must_include_product_title": True,
            "must_include_previous_price_line": True,
            "must_include_current_price_line": True,
            "must_include_discount_line_when_available": True,
            "must_include_url": True,
            "must_include_urgency_footer": True,
            "previous_price_should_be_strikethrough": True,
            "current_price_should_be_highlighted": True,
        },
        "headline_hint": None,
        "hook_hint": None,
        "min_relevant_discount_pct": MIN_RELEVANT_DISCOUNT_PCT,
    }


def generate_payloads(
    db_path: str,
    marketplace: str | None,
    query: str | None,
    limit: int,
    only_lowest: bool,
    min_relevant_discount_pct: float,
) -> dict[str, Any]:
    report = load_report(db_path, marketplace, query, limit * 3)
    items = report["items"]
    if only_lowest:
        items = [item for item in items if item["is_at_lowest_price"]]
    items = items[:limit]
    return {
        "items": [
            build_payload(item, min_relevant_discount_pct) for item in items
        ],
        "count": len(items),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate structured alert payloads from stored price history.")
    parser.add_argument("--db-path", default=str(ROOT / "data" / "price_history.sqlite3"), help="SQLite database path")
    parser.add_argument("--marketplace", help="Optional marketplace filter")
    parser.add_argument("--query", help="Optional exact query filter")
    parser.add_argument("--limit", type=int, default=5, help="Maximum products to include")
    parser.add_argument("--only-lowest", action="store_true", help="Include only products currently at their lowest price")
    parser.add_argument(
        "--min-relevant-discount-pct",
        type=float,
        default=MIN_RELEVANT_DISCOUNT_PCT,
        help="Minimum discount percentage to mark an alert as actionable",
    )
    args = parser.parse_args()

    print(
        json.dumps(
            generate_payloads(
                args.db_path,
                args.marketplace,
                args.query,
                args.limit,
                args.only_lowest,
                args.min_relevant_discount_pct,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
