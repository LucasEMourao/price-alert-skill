#!/usr/bin/env python3

"""Shared utilities for the price-alert-skill."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.adapters.json_sent_deals_repository import JSONSentDealsRepository
from core.domain.dedup_policy import (
    build_sent_record as domain_build_sent_record,
    can_send_again as domain_can_send_again,
    clean_old_deals as domain_clean_old_deals,
    deal_dedup_key as domain_deal_dedup_key,
    deal_offer_key as domain_deal_offer_key,
    deal_product_key as domain_deal_product_key,
    get_latest_sent_for_product as domain_get_latest_sent_for_product,
    get_sent_record as domain_get_sent_record,
    normalize_sent_deals_data as domain_normalize_sent_deals_data,
    normalize_sent_record as domain_normalize_sent_record,
)
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
    return domain_deal_dedup_key(deal)


def deal_product_key(deal: dict[str, Any]) -> str:
    """Resolve the stable product key for a deal."""
    return domain_deal_product_key(deal)


def deal_offer_key(deal: dict[str, Any]) -> str:
    """Resolve the stable offer key for a deal."""
    return domain_deal_offer_key(deal)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_SENT_DEALS_REPOSITORY = JSONSentDealsRepository(
    sent_deals_file_getter=lambda: SENT_DEALS_FILE,
    cadence_config_getter=lambda: CADENCE_CONFIG,
    retention_days_getter=lambda: DEDUP_RETENTION_DAYS,
    now_fn=_utc_now,
)


def _normalize_sent_record(key: str, value: Any) -> dict[str, Any]:
    """Normalize legacy sent-deal formats to the richer metadata shape."""
    return domain_normalize_sent_record(key, value)


def normalize_sent_deals_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize sent-deal payloads loaded from disk or tests."""
    return domain_normalize_sent_deals_data(data)


def load_sent_deals() -> dict[str, Any]:
    """Load sent deals from disk, return empty structure if missing."""
    return _SENT_DEALS_REPOSITORY.load_sent_deals()


def save_sent_deals(data: dict[str, Any]) -> None:
    """Persist sent deals to disk."""
    _SENT_DEALS_REPOSITORY.save_sent_deals(data)


def clean_old_deals(
    data: dict[str, Any],
    max_age_days: int = DEDUP_RETENTION_DAYS,
) -> dict[str, Any]:
    """Remove deals older than max_age_days."""
    return _SENT_DEALS_REPOSITORY.clean_old_deals(data, max_age_days=max_age_days)


def build_sent_record(
    deal: dict[str, Any],
    *,
    sent_at: str | None = None,
) -> dict[str, Any]:
    """Build the persisted metadata record for a sent deal."""
    return domain_build_sent_record(deal, sent_at=sent_at or _utc_now().isoformat())


def get_sent_record(
    sent_data: dict[str, Any],
    offer_key: str,
) -> dict[str, Any] | None:
    """Return the exact sent record for an offer key if present."""
    return domain_get_sent_record(sent_data, offer_key)


def get_latest_sent_for_product(
    sent_data: dict[str, Any],
    product_key: str,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    """Return the latest sent record for a product key."""
    return domain_get_latest_sent_for_product(sent_data, product_key)


def can_send_again(
    deal: dict[str, Any],
    sent_data: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when the deal is eligible to be sent again."""
    return _SENT_DEALS_REPOSITORY.can_send_again(deal, sent_data, now=now)


def filter_new_deals(
    deals: list[dict[str, Any]],
    sent_data: dict[str, Any] | None = None,
    auto_save: bool = True,
    mark_as_sent: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter out deals already sent in previous runs."""
    return _SENT_DEALS_REPOSITORY.filter_new_deals(
        deals,
        sent_data,
        auto_save=auto_save,
        mark_as_sent=mark_as_sent,
    )


def mark_deals_as_sent(
    deals: list[dict[str, Any]],
    sent_data: dict[str, Any] | None = None,
    auto_save: bool = True,
) -> dict[str, Any]:
    """Persist deals as sent after the downstream action succeeds."""
    return _SENT_DEALS_REPOSITORY.mark_deals_as_sent(
        deals,
        sent_data,
        auto_save=auto_save,
    )
