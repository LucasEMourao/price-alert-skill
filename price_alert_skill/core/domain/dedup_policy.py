"""Pure deduplication and resend policy helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def deal_dedup_key(deal: dict[str, Any]) -> str:
    """Resolve the stable deduplication key for a deal."""
    return deal.get("dedup_key") or deal["url"]


def deal_product_key(deal: dict[str, Any]) -> str:
    """Resolve the stable product key for a deal."""
    return deal.get("product_key") or deal_dedup_key(deal)


def deal_offer_key(deal: dict[str, Any]) -> str:
    """Resolve the stable offer key for a deal."""
    return deal.get("offer_key") or deal_dedup_key(deal)


def normalize_sent_record(key: str, value: Any) -> dict[str, Any]:
    """Normalize legacy sent-deal formats to the richer metadata shape."""
    if isinstance(value, dict):
        lane = value.get("lane")
        if lane is None and value.get("is_super_promo"):
            lane = "urgent"
        return {
            "product_key": value.get("product_key") or key,
            "category": value.get("category", ""),
            "sent_at": value.get("sent_at") or value.get("timestamp") or value.get("ts"),
            "discount_pct": value.get("discount_pct"),
            "savings_brl": value.get("savings_brl"),
            "is_super_promo": bool(value.get("is_super_promo", False)),
            "lane": lane or "normal",
            "title": value.get("title", ""),
            "current_price": value.get("current_price"),
        }

    return {
        "product_key": key,
        "category": "",
        "sent_at": value,
        "discount_pct": None,
        "savings_brl": None,
        "is_super_promo": False,
        "lane": "normal",
        "title": "",
        "current_price": None,
    }


def normalize_sent_deals_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize sent-deal payloads loaded from disk or tests."""
    if not data:
        return {"sent": {}, "last_cleaned": None}

    sent = data.get("sent", {})
    normalized_sent = {
        key: normalize_sent_record(key, value)
        for key, value in sent.items()
    }
    return {
        "sent": normalized_sent,
        "last_cleaned": data.get("last_cleaned"),
    }


def clean_old_deals(
    data: dict[str, Any],
    *,
    now: datetime,
    max_age_days: int,
) -> dict[str, Any]:
    """Remove deals older than max_age_days."""
    data = normalize_sent_deals_data(data)
    cutoff = now - timedelta(days=max_age_days)

    cleaned = {}
    for key, metadata in data.get("sent", {}).items():
        sent_at = metadata.get("sent_at")
        if not sent_at:
            continue
        if datetime.fromisoformat(sent_at) >= cutoff:
            cleaned[key] = metadata

    data["sent"] = cleaned
    data["last_cleaned"] = now.isoformat()
    return data


def build_sent_record(
    deal: dict[str, Any],
    *,
    sent_at: str,
) -> dict[str, Any]:
    """Build the persisted metadata record for a sent deal."""
    return {
        "product_key": deal_product_key(deal),
        "category": deal.get("category", ""),
        "sent_at": sent_at,
        "discount_pct": deal.get("discount_pct"),
        "savings_brl": deal.get("savings_brl"),
        "is_super_promo": bool(deal.get("lane") == "urgent" or deal.get("is_super_promo", False)),
        "lane": deal.get("lane", "normal"),
        "title": deal.get("title", ""),
        "current_price": deal.get("current_price"),
    }


def get_sent_record(
    sent_data: dict[str, Any],
    offer_key: str,
) -> dict[str, Any] | None:
    """Return the exact sent record for an offer key if present."""
    data = normalize_sent_deals_data(sent_data)
    return data.get("sent", {}).get(offer_key)


def get_latest_sent_for_product(
    sent_data: dict[str, Any],
    product_key: str,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    """Return the latest sent record for a product key."""
    latest_key = None
    latest_record = None
    latest_timestamp = None

    for offer_key, metadata in normalize_sent_deals_data(sent_data).get("sent", {}).items():
        if metadata.get("product_key") != product_key:
            continue
        sent_at = metadata.get("sent_at")
        if not sent_at:
            continue
        timestamp = datetime.fromisoformat(sent_at)
        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp
            latest_key = offer_key
            latest_record = metadata

    return latest_key, latest_record


def can_send_again(
    deal: dict[str, Any],
    sent_data: dict[str, Any],
    *,
    now: datetime,
    cadence_config: dict[str, Any],
) -> bool:
    """Return True when the deal is eligible to be sent again."""
    offer_key = deal_offer_key(deal)
    product_key = deal_product_key(deal)
    same_offer_record = get_sent_record(sent_data, offer_key)

    if same_offer_record:
        sent_at = datetime.fromisoformat(same_offer_record["sent_at"])
        age = now - sent_at
        cooldown_hours = cadence_config["urgent_offer_cooldown_hours"]
        if not (
            deal.get("lane") == "urgent"
            or deal.get("is_super_promo")
            or same_offer_record.get("lane") == "urgent"
            or same_offer_record.get("is_super_promo")
        ):
            cooldown_hours = cadence_config["same_offer_cooldown_hours"]
        return age >= timedelta(hours=cooldown_hours)

    latest_offer_key, latest_product_record = get_latest_sent_for_product(sent_data, product_key)
    if not latest_offer_key or not latest_product_record:
        return True

    if deal.get("lane") == "urgent" or deal.get("is_super_promo"):
        return True

    current_discount = float(deal.get("discount_pct") or 0.0)
    current_savings = float(deal.get("savings_brl") or 0.0)
    previous_discount = float(latest_product_record.get("discount_pct") or 0.0)
    previous_savings = float(latest_product_record.get("savings_brl") or 0.0)

    if current_discount - previous_discount >= float(cadence_config["min_discount_improvement_points"]):
        return True

    if current_savings - previous_savings >= float(cadence_config["min_savings_improvement_brl"]):
        return True

    sent_at = latest_product_record.get("sent_at")
    if not sent_at:
        return True

    return now - datetime.fromisoformat(sent_at) >= timedelta(
        hours=cadence_config["same_offer_cooldown_hours"]
    )
