#!/usr/bin/env python3

"""Shared utilities for the price-alert-skill."""

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
    """Format price as R$ XXXX.XX (dot as decimal separator)."""
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

    emoji = detect_category_emoji(title, query)

    if len(title) > 120:
        title = title[:117] + "..."

    price_today = format_price_brl(current_price)

    lines = [
        f"{emoji} OFERTA DO DIA 👇",
        "",
        f"{emoji} {title}",
        "",
        f"🎯 Hoje: {price_today}",
    ]

    if previous_price and discount_pct:
        price_was = format_price_brl(previous_price)
        discount_int = int(round(discount_pct))
        lines.append(f"📉 Era: {price_was}")
        lines.append(f"🔥 Desconto: {discount_int}% OFF")

    lines.extend([
        "",
        "🛍️ Comprar aqui:",
        url,
        "",
        "🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.",
    ])

    return "\n".join(lines)
