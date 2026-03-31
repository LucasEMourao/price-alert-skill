#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Any

from generate_alert_payloads import generate_payloads

ROOT = Path(__file__).resolve().parents[1]


def discount_badge(discount_pct: float | None) -> str:
    if discount_pct is None:
        return "SEM HISTORICO DE PRECO"
    if discount_pct >= 15:
        return f"🟠 {discount_pct:.0f}% OFF!"
    if discount_pct > 0:
        return f"🟢 {discount_pct:.0f}% OFF!"
    return "SEM DESCONTO RELEVANTE"


def format_single_item(item: dict[str, Any], title: str) -> str:
    previous = item.get("previous_price_reference", {})
    lines = [
        item.get("headline_hint") or title,
        item["product_title"],
        "",
    ]

    if previous.get("text"):
        lines.append(f"De: ~{previous['text']}~")
    else:
        lines.append("De: ~sem histórico suficiente~")

    lines.extend(
        [
            f"Por: *{item['current_price_text']}*" if item.get("current_price_text") else "Por: *sem preço disponível*",
            discount_badge(item.get("discount_pct")),
            "Garanta o seu aqui:",
            item["product_url"],
            "Preço pode mudar a qualquer momento. Se curtiu, não deixa pra depois.",
        ]
    )

    zoom = item.get("zoom_baseline") or {}
    if zoom.get("median_price_text") is not None:
        lines.extend(
            [
                "",
                f"Base Zoom: mediana {zoom['median_price_text']}",
            ]
        )

    return "\n".join(lines)


def format_items(items: list[dict[str, Any]], title: str) -> str:
    if not items:
        return "Sem descontos encontrados no momento."

    return "\n\n".join(format_single_item(item, title) for item in items)


def render_messages(
    db_path: str,
    marketplace: str | None,
    query: str | None,
    limit: int,
    only_lowest: bool,
    title: str,
    min_relevant_discount_pct: float,
) -> str:
    payloads = generate_payloads(
        db_path,
        marketplace,
        query,
        limit,
        only_lowest,
        min_relevant_discount_pct,
    )
    items = [item for item in payloads["items"] if item.get("actionable")]
    return format_items(items, title)


def main() -> None:
    parser = argparse.ArgumentParser(description="Format WhatsApp-ready alert/report text from SQLite history.")
    parser.add_argument("--db-path", default=str(ROOT / "data" / "price_history.sqlite3"), help="SQLite database path")
    parser.add_argument("--marketplace", help="Optional marketplace filter")
    parser.add_argument("--query", help="Optional exact query filter")
    parser.add_argument("--limit", type=int, default=5, help="Maximum products to include")
    parser.add_argument("--only-lowest", action="store_true", help="Include only products currently at their lowest price")
    parser.add_argument(
        "--title",
        default="OFERTA NO RADAR!",
        help="Headline shown above each product block",
    )
    parser.add_argument(
        "--min-discount-pct",
        type=float,
        default=5.0,
        help="Minimum discount percentage required to show an alert",
    )
    args = parser.parse_args()

    print(
        render_messages(
            args.db_path,
            args.marketplace,
            args.query,
            args.limit,
            args.only_lowest,
            args.title,
            args.min_discount_pct,
        )
    )


if __name__ == "__main__":
    main()
