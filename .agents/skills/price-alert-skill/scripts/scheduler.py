#!/usr/bin/env python3

"""Price monitor scheduler — updates all watchlists every N minutes,
detects deals below average, and generates WhatsApp messages.

Usage:
  python3 scheduler.py --interval 5
  python3 scheduler.py --once  # Run once and exit
"""

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from detect_deals import detect_deals
from format_deal_messages import format_all_deals
from monitor_query import monitor_query


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
MESSAGES_DIR = ROOT / "data" / "messages"


def load_active_watchlists(db_path: str) -> list[dict[str, Any]]:
    """Load all active watchlists from SQLite."""
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, query, queries_json, marketplaces_json "
            "FROM watchlists WHERE active = 1"
        ).fetchall()
        watchlists = []
        for row in rows:
            queries = json.loads(row["queries_json"]) if row["queries_json"] else [row["query"]]
            marketplaces = json.loads(row["marketplaces_json"]) if row["marketplaces_json"] else ["amazon_br", "mercadolivre_br"]
            watchlists.append({
                "id": int(row["id"]),
                "name": row["name"],
                "queries": queries,
                "marketplaces": marketplaces,
            })
        return watchlists
    finally:
        conn.close()


def run_update_cycle(db_path: str) -> dict[str, Any]:
    """Run one full update cycle: scrape all watchlists, detect deals, format messages."""
    now = datetime.now(timezone.utc)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Starting update cycle...")

    # 1. Load watchlists
    watchlists = load_active_watchlists(db_path)
    print(f"  Found {len(watchlists)} active watchlists")

    # 2. Scrape all marketplaces for all queries
    total_stored = 0
    total_errors = []
    for wl in watchlists:
        for marketplace in wl["marketplaces"]:
            for query in wl["queries"]:
                try:
                    result = monitor_query(
                        marketplace=marketplace,
                        query=query,
                        db_path=Path(db_path),
                        max_results=10,
                        session_id=None,
                    )
                    stored = result.get("stored_products", 0)
                    total_stored += stored
                    errors = result.get("source_errors", [])
                    if errors:
                        total_errors.extend(errors)
                    if stored > 0:
                        print(f"  ✓ {marketplace} / {query}: {stored} products")
                except Exception as exc:
                    total_errors.append(f"{marketplace}/{query}: {exc}")
                    print(f"  ✗ {marketplace} / {query}: {exc}")

    print(f"  Total stored: {total_stored} snapshots")

    # 3. Detect deals below average
    deals = detect_deals(
        db_path=db_path,
        min_discount_pct=5.0,
        min_snapshots=2,
        lookback_days=7,
    )
    print(f"  Deals detected: {len(deals)}")

    # 4. Format WhatsApp messages
    messages = format_all_deals(deals)
    if messages:
        print(f"  Messages generated: {len(messages)}")
        # Save to file
        MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        output_path = MESSAGES_DIR / f"alerts_{ts}.json"
        output_path.write_text(json.dumps(
            {"messages": messages, "count": len(messages), "generated_at": now.isoformat()},
            ensure_ascii=False, indent=2,
        ))
        print(f"  Saved to: {output_path}")

        # Print messages
        for msg in messages:
            print(f"\n{'='*50}")
            print(msg["message"])
            print(f"{'='*50}")
    else:
        print("  No deals found this cycle.")

    return {
        "timestamp": now.isoformat(),
        "watchlists": len(watchlists),
        "snapshots_stored": total_stored,
        "deals_detected": len(deals),
        "messages_generated": len(messages),
        "errors": total_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Price monitor scheduler.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--interval", type=int, default=5, help="Minutes between updates")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        run_update_cycle(args.db_path)
        return

    print(f"Starting scheduler: updating every {args.interval} minutes")
    print(f"Database: {args.db_path}")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            run_update_cycle(args.db_path)
        except KeyboardInterrupt:
            print("\nScheduler stopped.")
            break
        except Exception as exc:
            print(f"  Error in cycle: {exc}")

        next_run = datetime.now(timezone.utc)
        print(f"\nNext update in {args.interval} minutes...")
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
