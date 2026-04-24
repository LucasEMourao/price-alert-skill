#!/usr/bin/env python3

"""Shared utilities for the price-alert-skill."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from deal_selection import CADENCE_CONFIG


CATEGORY_EMOJIS = {
    "mouse": "🖱️",
    "teclado": "⌨️",
    "headset": "🎧",
    "fone": "🎧",
    "monitor": "🖥️",
    "ssd": "💾",
    "hd": "💾",
    "nvme": "💾",
    "memoria": "🧩",
    "ram": "🧩",
    "ddr": "🧩",
    "placa": "🎮",
    "rtx": "🎮",
    "gpu": "🎮",
    "notebook": "💻",
    "laptop": "💻",
    "gabinete": "🏠",
    "fonte": "⚡",
    "cooler": "❄️",
    "water": "❄️",
    "cadeira": "🪑",
    "mousepad": "🎯",
    "webcam": "📷",
    "controle": "🎮",
    "gamepad": "🎮",
}

DEFAULT_EMOJI = "🎮"


def detect_category_emoji(title: str, query: str) -> str:
    """Detect product category and return matching emoji."""
    combined = f"{title} {query}".lower()
    for keyword, emoji in CATEGORY_EMOJIS.items():
        if keyword in combined:
            return emoji
    return DEFAULT_EMOJI


def format_price_brl(value: float) -> str:
    """Format price as R$ X.XXX,XX (Brazilian convention)."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def calculate_discount(current_price: float, list_price: float) -> float | None:
    """Calculate discount percentage if list_price is higher than current_price."""
    if list_price and current_price and list_price > current_price:
        return round(((list_price - current_price) / list_price) * 100, 1)
    return None


def format_deal_message(deal: dict[str, Any]) -> str:
    """Format a single deal as WhatsApp message."""
    title = deal["title"]
    current_price = deal["current_price"]
    url = deal["url"]
    discount_pct = deal["discount_pct"]
    previous_price = deal.get("previous_price")
    query = deal.get("query", "")

    category_emoji = detect_category_emoji(title, query)

    if len(title) > 120:
        title = title[:117] + "..."

    price_today = format_price_brl(current_price)

    lines = [
        f"{category_emoji} OFERTA DO DIA 👇",
        "",
        f"{category_emoji} {title}",
    ]

    if previous_price and discount_pct:
        price_was = format_price_brl(previous_price)
        discount_int = int(round(discount_pct))
        lines.extend([
            "",
            f"🔥 {discount_int}% OFF",
            f"💰 Antes: ~{price_was}~",
            f"🎯 Hoje: {price_today}",
        ])
    else:
        lines.extend([
            "",
            f"🎯 Hoje: {price_today}",
        ])

    lines.extend([
        "",
        "🛍️ Comprar aqui:",
        url,
        "",
        "💸 Valores podem variar. Se entrar em estoque baixo, some rápido.",
    ])

    return "\n".join(lines)


ROOT = Path(__file__).resolve().parents[1]
SENT_DEALS_FILE = ROOT / "data" / "sent_deals.json"
DEDUP_RETENTION_DAYS = 7


def deal_fingerprint(deal: dict[str, Any]) -> str:
    """Generate a unique fingerprint for a deal based on URL and price."""
    raw = f"{deal['url']}|{deal['current_price']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def deal_dedup_key(deal: dict[str, Any]) -> str:
    """Resolve the stable deduplication key for a deal."""
    return deal.get("dedup_key") or deal["url"]


def deal_product_key(deal: dict[str, Any]) -> str:
    """Resolve the stable product key for a deal."""
    return deal.get("product_key") or deal_dedup_key(deal)


def deal_offer_key(deal: dict[str, Any]) -> str:
    """Resolve the stable offer key for a deal."""
    return deal.get("offer_key") or deal_dedup_key(deal)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_sent_record(key: str, value: Any) -> dict[str, Any]:
    """Normalize legacy sent-deal formats to the richer metadata shape."""
    if isinstance(value, dict):
        return {
            "product_key": value.get("product_key") or key,
            "category": value.get("category", ""),
            "sent_at": value.get("sent_at") or value.get("timestamp") or value.get("ts"),
            "discount_pct": value.get("discount_pct"),
            "savings_brl": value.get("savings_brl"),
            "is_super_promo": bool(value.get("is_super_promo", False)),
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
        "title": "",
        "current_price": None,
    }


def normalize_sent_deals_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize sent-deal payloads loaded from disk or tests."""
    if not data:
        return {"sent": {}, "last_cleaned": None}

    sent = data.get("sent", {})
    normalized_sent = {
        key: _normalize_sent_record(key, value)
        for key, value in sent.items()
    }
    return {
        "sent": normalized_sent,
        "last_cleaned": data.get("last_cleaned"),
    }


def load_sent_deals() -> dict[str, Any]:
    """Load sent deals from disk, return empty structure if missing."""
    if SENT_DEALS_FILE.exists():
        raw = json.loads(SENT_DEALS_FILE.read_text(encoding="utf-8"))
        return normalize_sent_deals_data(raw)
    return {"sent": {}, "last_cleaned": None}


def save_sent_deals(data: dict[str, Any]) -> None:
    """Persist sent deals to disk."""
    SENT_DEALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENT_DEALS_FILE.write_text(
        json.dumps(normalize_sent_deals_data(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clean_old_deals(
    data: dict[str, Any],
    max_age_days: int = DEDUP_RETENTION_DAYS,
) -> dict[str, Any]:
    """Remove deals older than max_age_days."""
    data = normalize_sent_deals_data(data)
    cutoff = _utc_now() - timedelta(days=max_age_days)

    cleaned = {}
    for key, metadata in data.get("sent", {}).items():
        sent_at = metadata.get("sent_at")
        if not sent_at:
            continue
        if datetime.fromisoformat(sent_at) >= cutoff:
            cleaned[key] = metadata

    data["sent"] = cleaned
    data["last_cleaned"] = _utc_now().isoformat()
    return data


def build_sent_record(
    deal: dict[str, Any],
    *,
    sent_at: str | None = None,
) -> dict[str, Any]:
    """Build the persisted metadata record for a sent deal."""
    return {
        "product_key": deal_product_key(deal),
        "category": deal.get("category", ""),
        "sent_at": sent_at or _utc_now().isoformat(),
        "discount_pct": deal.get("discount_pct"),
        "savings_brl": deal.get("savings_brl"),
        "is_super_promo": bool(deal.get("is_super_promo", False)),
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
    sent_data: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when the deal is eligible to be sent again."""
    sent_data = clean_old_deals(sent_data or load_sent_deals())
    now = now or _utc_now()
    offer_key = deal_offer_key(deal)
    product_key = deal_product_key(deal)
    same_offer_record = get_sent_record(sent_data, offer_key)

    if same_offer_record:
        sent_at = datetime.fromisoformat(same_offer_record["sent_at"])
        age = now - sent_at
        cooldown_hours = CADENCE_CONFIG["super_offer_cooldown_hours"]
        if not (deal.get("is_super_promo") or same_offer_record.get("is_super_promo")):
            cooldown_hours = CADENCE_CONFIG["same_offer_cooldown_hours"]
        return age >= timedelta(hours=cooldown_hours)

    latest_offer_key, latest_product_record = get_latest_sent_for_product(sent_data, product_key)
    if not latest_offer_key or not latest_product_record:
        return True

    if deal.get("is_super_promo"):
        return True

    current_discount = float(deal.get("discount_pct") or 0.0)
    current_savings = float(deal.get("savings_brl") or 0.0)
    previous_discount = float(latest_product_record.get("discount_pct") or 0.0)
    previous_savings = float(latest_product_record.get("savings_brl") or 0.0)

    if current_discount - previous_discount >= float(CADENCE_CONFIG["min_discount_improvement_points"]):
        return True

    if current_savings - previous_savings >= float(CADENCE_CONFIG["min_savings_improvement_brl"]):
        return True

    sent_at = latest_product_record.get("sent_at")
    if not sent_at:
        return True

    return now - datetime.fromisoformat(sent_at) >= timedelta(
        hours=CADENCE_CONFIG["same_offer_cooldown_hours"]
    )


def filter_new_deals(
    deals: list[dict[str, Any]],
    sent_data: dict[str, Any] | None = None,
    auto_save: bool = True,
    mark_as_sent: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter out deals already sent in previous runs."""
    if sent_data is None:
        sent_data = load_sent_deals()

    sent_data = clean_old_deals(sent_data)
    new_deals = []
    now_iso = _utc_now().isoformat()

    for deal in deals:
        if can_send_again(deal, sent_data, now=datetime.fromisoformat(now_iso)):
            if mark_as_sent:
                sent_data["sent"][deal_offer_key(deal)] = build_sent_record(deal, sent_at=now_iso)
            new_deals.append(deal)

    if auto_save:
        save_sent_deals(sent_data)

    return new_deals, sent_data


def mark_deals_as_sent(
    deals: list[dict[str, Any]],
    sent_data: dict[str, Any] | None = None,
    auto_save: bool = True,
) -> dict[str, Any]:
    """Persist deals as sent after the downstream action succeeds."""
    if sent_data is None:
        sent_data = load_sent_deals()

    sent_data = clean_old_deals(sent_data)
    now_iso = _utc_now().isoformat()

    for deal in deals:
        sent_data["sent"][deal_offer_key(deal)] = build_sent_record(deal, sent_at=now_iso)

    if auto_save:
        save_sent_deals(sent_data)

    return sent_data
