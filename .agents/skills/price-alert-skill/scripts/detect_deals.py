#!/usr/bin/env python3

"""Detect products with prices below their historical average.

Queries SQLite for products where the current price is at least N% below
the average of their last M snapshots. Outputs a list of alert payloads.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"

# Thresholds
MIN_DISCOUNT_PCT = 5.0
MIN_SNAPSHOTS = 3
LOOKBACK_DAYS = 7


def detect_deals(
    db_path: str,
    min_discount_pct: float = MIN_DISCOUNT_PCT,
    min_snapshots: int = MIN_SNAPSHOTS,
    lookback_days: int = LOOKBACK_DAYS,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    """Find products where current price is below historical average."""
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row

    try:
        # Get products with their latest price and average
        query = """
        WITH latest AS (
            SELECT
                ps.product_id,
                ps.price AS current_price,
                ps.price_text AS current_price_text,
                ps.captured_at AS latest_captured_at,
                ps.query AS last_query
            FROM price_snapshots ps
            INNER JOIN (
                SELECT product_id, MAX(captured_at) AS max_ts
                FROM price_snapshots
                WHERE price IS NOT NULL
                GROUP BY product_id
            ) latest_ts ON ps.product_id = latest_ts.product_id
                       AND ps.captured_at = latest_ts.max_ts
            WHERE ps.price IS NOT NULL
        ),
        history AS (
            SELECT
                ps.product_id,
                AVG(ps.price) AS avg_price,
                MIN(ps.price) AS min_price,
                COUNT(ps.id) AS snapshot_count
            FROM price_snapshots ps
            WHERE ps.price IS NOT NULL
              AND ps.captured_at > datetime('now', ?)
            GROUP BY ps.product_id
            HAVING COUNT(ps.id) >= ?
        )
        SELECT
            p.id AS product_id,
            p.title,
            p.url,
            p.image_url,
            p.marketplace,
            l.current_price,
            l.current_price_text,
            l.latest_captured_at,
            l.last_query,
            h.avg_price,
            h.min_price,
            h.snapshot_count,
            ROUND(((h.avg_price - l.current_price) / h.avg_price) * 100, 1) AS discount_pct
        FROM latest l
        JOIN history h ON l.product_id = h.product_id
        JOIN products p ON p.id = l.product_id
        WHERE l.current_price < h.avg_price * (1 - ? / 100.0)
        """

        params: list[Any] = [
            f"-{lookback_days} days",
            min_snapshots,
            min_discount_pct,
        ]

        if marketplace:
            query += " AND p.marketplace = ?"
            params.append(marketplace)

        query += " ORDER BY discount_pct DESC"

        rows = conn.execute(query, params).fetchall()

        deals = []
        for row in rows:
            discount_pct = float(row["discount_pct"])
            avg_price = float(row["avg_price"])
            current_price = float(row["current_price"])

            deals.append({
                "product_id": int(row["product_id"]),
                "title": row["title"],
                "url": row["url"],
                "image_url": row["image_url"],
                "marketplace": row["marketplace"],
                "current_price": current_price,
                "current_price_text": row["current_price_text"],
                "avg_price": round(avg_price, 2),
                "min_price": float(row["min_price"]),
                "discount_pct": discount_pct,
                "snapshot_count": int(row["snapshot_count"]),
                "last_query": row["last_query"],
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return deals
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect products with prices below historical average.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--min-discount", type=float, default=MIN_DISCOUNT_PCT, help="Minimum discount %% to alert")
    parser.add_argument("--min-snapshots", type=int, default=MIN_SNAPSHOTS, help="Minimum snapshots for comparison")
    parser.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS, help="Days of history to consider")
    parser.add_argument("--marketplace", help="Filter by marketplace")
    args = parser.parse_args()

    deals = detect_deals(
        db_path=args.db_path,
        min_discount_pct=args.min_discount,
        min_snapshots=args.min_snapshots,
        lookback_days=args.lookback_days,
        marketplace=args.marketplace,
    )

    print(json.dumps({"deals": deals, "count": len(deals)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
