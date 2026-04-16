#!/usr/bin/env python3

"""Shared utilities for the price-alert-skill."""

import hashlib
import json
from pathlib import Path
from typing import Any


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
    """Format a single deal as WhatsApp message.

    Format (matches client's preferred style):
        🎸 OFERTA DO DIA 👇

        🎚️ {PRODUCT TITLE}

        🔥 {DISCOUNT}% OFF
        💰 Antes: R$ {OLD PRICE}
        🎯 Hoje: R$ {CURRENT PRICE}

        🛍️ Comprar aqui:
        {LINK}

        🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
    """
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


def load_sent_deals() -> dict[str, Any]:
    """Load sent deals from disk, return empty structure if missing."""
    if SENT_DEALS_FILE.exists():
        return json.loads(SENT_DEALS_FILE.read_text())
    return {"sent": {}, "last_cleaned": None}


def save_sent_deals(data: dict[str, Any]) -> None:
    """Persist sent deals to disk."""
    SENT_DEALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENT_DEALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def clean_old_deals(data: dict[str, Any], max_age_days: int = DEDUP_RETENTION_DAYS) -> dict[str, Any]:
    """Remove deals older than max_age_days."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_ts = cutoff.isoformat()

    cleaned = {
        url: ts
        for url, ts in data.get("sent", {}).items()
        if ts >= cutoff_ts
    }
    data["sent"] = cleaned
    data["last_cleaned"] = datetime.now(timezone.utc).isoformat()
    return data


def filter_new_deals(
    deals: list[dict[str, Any]],
    sent_data: dict[str, Any] | None = None,
    auto_save: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter out deals already sent in previous runs.

    Returns (new_deals, updated_sent_data).
    """
    from datetime import datetime, timezone

    if sent_data is None:
        sent_data = load_sent_deals()

    sent_data = clean_old_deals(sent_data)
    sent_urls = set(sent_data.get("sent", {}).keys())

    new_deals = []
    now = datetime.now(timezone.utc).isoformat()

    for deal in deals:
        url = deal["url"]
        if url not in sent_urls:
            sent_data["sent"][url] = now
            new_deals.append(deal)

    if auto_save:
        save_sent_deals(sent_data)

    return new_deals, sent_data
