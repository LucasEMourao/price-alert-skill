#!/usr/bin/env python3

"""Format deal alerts as WhatsApp-ready messages.

Uses the template defined in PLANO.md:
  {emoji} OFERTA DO DIA
  {product name}
  Hoje: R$ X
  (optional) Era: R$ Y / Desconto: Z% OFF
  Comprar aqui: {link}
  Aviso de escassez
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

# Category emoji mapping
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


def format_deal_message(deal: dict[str, Any]) -> str:
    """Format a single deal as WhatsApp message."""
    title = deal["title"]
    current_price = deal["current_price"]
    url = deal["url"]
    discount_pct = deal.get("discount_pct", 0)
    avg_price = deal.get("avg_price")
    query = deal.get("last_query", "")

    emoji = detect_category_emoji(title, query)

    # Truncate long titles
    if len(title) > 120:
        title = title[:117] + "..."

    # Format prices
    price_today = format_price_brl(current_price)

    lines = [
        f"{emoji} OFERTA DO DIA 👇",
        "",
        f"{emoji} {title}",
        "",
        f"🎯 Hoje: {price_today}",
    ]

    # Add comparison if discount >= 5%
    if discount_pct >= 5 and avg_price:
        price_was = format_price_brl(avg_price)
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


def format_all_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format all deals into WhatsApp messages."""
    messages = []
    for deal in deals:
        message = format_deal_message(deal)
        messages.append({
            "product_id": deal["product_id"],
            "title": deal["title"],
            "marketplace": deal["marketplace"],
            "current_price": deal["current_price"],
            "discount_pct": deal.get("discount_pct", 0),
            "message": message,
        })
    return messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Format deal alerts as WhatsApp messages.")
    parser.add_argument("--input", help="Path to detect_deals JSON output (reads stdin if omitted)")
    parser.add_argument("--output", help="Path to write formatted messages JSON")
    args = parser.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text())
    else:
        import sys
        data = json.loads(sys.stdin.read())

    deals = data.get("deals", [])
    messages = format_all_deals(deals)

    result = {"messages": messages, "count": len(messages)}

    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Wrote {len(messages)} messages to {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
