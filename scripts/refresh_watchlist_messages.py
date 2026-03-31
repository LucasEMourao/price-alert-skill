#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

from format_whatsapp_alerts import render_messages
from update_watchlist import run_watchlist_updates

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"


def load_watchlist_queries(db_path: str, watchlist_id: int) -> list[tuple[str | None, str]]:
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        watchlist = conn.execute(
            "SELECT query, queries_json FROM watchlists WHERE id = ?",
            (watchlist_id,),
        ).fetchone()
        if not watchlist:
            return []
        queries = json.loads(watchlist["queries_json"]) if watchlist["queries_json"] else [watchlist["query"]]
        products = conn.execute(
            "SELECT DISTINCT marketplace, normalized_query FROM watchlist_products WHERE watchlist_id = ?",
            (watchlist_id,),
        ).fetchall()
    finally:
        conn.close()

    pairs: list[tuple[str | None, str]] = []
    seen = set()
    for product in products:
        key = (product["marketplace"], product["normalized_query"])
        if product["normalized_query"] and key not in seen:
            seen.add(key)
            pairs.append(key)
    for query in queries:
        key = (None, query)
        if query and key not in seen:
            seen.add(key)
            pairs.append(key)
    return pairs


def render_watchlist_messages(
    db_path: str,
    watchlist_id: int,
    limit: int,
    min_discount_pct: float,
) -> str:
    messages: list[str] = []
    for marketplace, query in load_watchlist_queries(db_path, watchlist_id):
        rendered = (
            render_messages(
                db_path,
                marketplace,
                query,
                limit,
                False,
                "OFERTA NO RADAR!",
                min_discount_pct,
            )
            .strip()
        )
        if rendered and rendered != "Sem descontos encontrados no momento.":
            messages.append(rendered)
    return "\n\n".join(messages) if messages else "Sem descontos encontrados no momento."


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a watchlist refresh and print only final WhatsApp messages.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--watchlist-id", type=int, help="Optional single watchlist id")
    parser.add_argument("--force", action="store_true", help="Run even if the watchlist is not due")
    parser.add_argument("--limit", type=int, default=3, help="Maximum messages per query")
    parser.add_argument(
        "--min-discount-pct",
        type=float,
        default=5.0,
        help="Minimum discount percentage to keep alerts",
    )
    args = parser.parse_args()

    result = run_watchlist_updates(args.db_path, args.watchlist_id, args.force)
    watchlist_ids = [entry["watchlist_id"] for entry in result.get("results", []) if entry.get("status") == "success"]
    if not watchlist_ids and args.watchlist_id is not None:
        watchlist_ids = [args.watchlist_id]

    blocks = [
        render_watchlist_messages(
            args.db_path,
            watchlist_id,
            args.limit,
            args.min_discount_pct,
        )
        for watchlist_id in watchlist_ids
    ]
    messages = [block for block in blocks if block and block != "Sem descontos encontrados no momento."]
    print("\n\n".join(messages) if messages else "Sem descontos encontrados no momento.")


if __name__ == "__main__":
    main()
