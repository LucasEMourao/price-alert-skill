#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS external_price_history (
            id INTEGER PRIMARY KEY,
            product_id INTEGER,
            source TEXT NOT NULL,
            source_product_id TEXT,
            source_url TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            title TEXT,
            image_url TEXT,
            brand TEXT,
            model TEXT,
            current_best_price REAL,
            current_best_price_text TEXT,
            low_offer_price REAL,
            high_offer_price REAL,
            offer_count INTEGER,
            median_price REAL,
            tip_description TEXT,
            tip_window_start TEXT,
            tip_window_end TEXT,
            tip_text TEXT,
            visible_history_ranges_json TEXT,
            raw_summary_json TEXT
        );

        CREATE TABLE IF NOT EXISTS product_external_links (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            source_product_id TEXT,
            source_url TEXT NOT NULL,
            matched_title TEXT,
            score REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(product_id, source)
        );

        CREATE TABLE IF NOT EXISTS alert_events (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            marketplace TEXT NOT NULL,
            query TEXT NOT NULL,
            reason TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,
            current_price REAL,
            reference_price REAL,
            discount_pct REAL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def fetch_rows(conn: sqlite3.Connection, marketplace: str | None, query: str | None, limit: int) -> list[sqlite3.Row]:
    filters: list[str] = []
    filter_params: list[Any] = []

    if marketplace:
        filters.append("p.marketplace = ?")
        filter_params.append(marketplace)

    if query:
        filters.append("s.query = ?")
        filter_params.append(query)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    sql = f"""
    WITH latest AS (
        SELECT
            s.product_id,
            MAX(s.captured_at) AS latest_captured_at
        FROM price_snapshots s
        JOIN products p ON p.id = s.product_id
        {where_clause}
        GROUP BY s.product_id
    ),
    priced AS (
        SELECT
            s.product_id,
            MIN(CASE WHEN s.price IS NOT NULL THEN s.price END) AS min_price,
            MAX(CASE WHEN s.price IS NOT NULL THEN s.price END) AS max_price,
            COUNT(CASE WHEN s.price IS NOT NULL THEN 1 END) AS priced_snapshots
        FROM price_snapshots s
        JOIN products p ON p.id = s.product_id
        {where_clause}
        GROUP BY s.product_id
    ),
    latest_zoom AS (
        SELECT
            eph.product_id,
            MAX(eph.captured_at) AS latest_captured_at
        FROM external_price_history eph
        WHERE eph.source = 'zoom_br'
        GROUP BY eph.product_id
    ),
    previous_priced AS (
        SELECT
            current_rows.product_id,
            current_rows.price AS previous_price,
            current_rows.price_text AS previous_price_text,
            current_rows.captured_at AS previous_captured_at
        FROM (
            SELECT
                s.product_id,
                s.price,
                s.price_text,
                s.captured_at,
                ROW_NUMBER() OVER (
                    PARTITION BY s.product_id
                    ORDER BY s.captured_at DESC
                ) AS rn
            FROM price_snapshots s
            WHERE s.price IS NOT NULL
        ) AS current_rows
        WHERE current_rows.rn = 2
    )
    SELECT
        p.id AS product_id,
        p.marketplace,
        p.external_id,
        p.title,
        p.url,
        p.image_url,
        s.query,
        s.captured_at,
        s.price,
        s.price_text,
        s.position,
        s.review_count,
        pp.previous_price,
        pp.previous_price_text,
        pp.previous_captured_at,
        priced.min_price,
        priced.max_price,
        priced.priced_snapshots,
        eph.current_best_price AS zoom_current_best_price,
        eph.low_offer_price AS zoom_low_offer_price,
        eph.high_offer_price AS zoom_high_offer_price,
        eph.offer_count AS zoom_offer_count,
        eph.median_price AS zoom_median_price,
        eph.tip_description AS zoom_tip_description,
        eph.tip_window_start AS zoom_tip_window_start,
        eph.tip_window_end AS zoom_tip_window_end,
        eph.tip_text AS zoom_tip_text
    FROM latest
    JOIN price_snapshots s
        ON s.product_id = latest.product_id
       AND s.captured_at = latest.latest_captured_at
    JOIN products p ON p.id = s.product_id
    JOIN priced ON priced.product_id = s.product_id
    LEFT JOIN previous_priced pp ON pp.product_id = s.product_id
    LEFT JOIN latest_zoom lz ON lz.product_id = s.product_id
    LEFT JOIN external_price_history eph
        ON eph.product_id = lz.product_id
       AND eph.captured_at = lz.latest_captured_at
       AND eph.source = 'zoom_br'
    ORDER BY
        CASE WHEN s.price IS NULL THEN 1 ELSE 0 END,
        ((s.price - priced.min_price) / NULLIF(priced.min_price, 0)) ASC,
        s.captured_at DESC
    LIMIT ?
    """
    params = filter_params + filter_params + [limit]
    return conn.execute(sql, params).fetchall()


def build_report(rows: list[sqlite3.Row]) -> dict[str, Any]:
    items = []
    for row in rows:
        current_price = row["price"]
        min_price = row["min_price"]
        drop_from_max_pct = None
        premium_vs_min_pct = None
        previous_price = row["previous_price"]
        discount_from_previous_pct = None

        if row["max_price"] and current_price is not None and row["max_price"] != 0:
            drop_from_max_pct = round(((row["max_price"] - current_price) / row["max_price"]) * 100, 2)
        if min_price and current_price is not None and min_price != 0:
            premium_vs_min_pct = round(((current_price - min_price) / min_price) * 100, 2)
        if previous_price and current_price is not None and previous_price != 0:
            discount_from_previous_pct = round(((previous_price - current_price) / previous_price) * 100, 2)

        items.append(
            {
                "product_id": row["product_id"],
                "marketplace": row["marketplace"],
                "external_id": row["external_id"],
                "title": row["title"],
                "url": row["url"],
                "query": row["query"],
                "captured_at": row["captured_at"],
                "current_price": current_price,
                "current_price_text": row["price_text"],
                "previous_price": previous_price,
                "previous_price_text": row["previous_price_text"],
                "previous_captured_at": row["previous_captured_at"],
                "discount_from_previous_pct": discount_from_previous_pct,
                "lowest_recorded_price": min_price,
                "highest_recorded_price": row["max_price"],
                "priced_snapshots": row["priced_snapshots"],
                "position": row["position"],
                "review_count": row["review_count"],
                "premium_vs_lowest_pct": premium_vs_min_pct,
                "drop_from_highest_pct": drop_from_max_pct,
                "is_at_lowest_price": current_price is not None and min_price is not None and current_price == min_price,
                "zoom_current_best_price": row["zoom_current_best_price"],
                "zoom_low_offer_price": row["zoom_low_offer_price"],
                "zoom_high_offer_price": row["zoom_high_offer_price"],
                "zoom_offer_count": row["zoom_offer_count"],
                "zoom_median_price": row["zoom_median_price"],
                "zoom_tip_description": row["zoom_tip_description"],
                "zoom_tip_window_start": row["zoom_tip_window_start"],
                "zoom_tip_window_end": row["zoom_tip_window_end"],
                "zoom_tip_text": row["zoom_tip_text"],
            }
        )

    return {
        "items": items,
        "count": len(items),
    }


def load_report(db_path: str, marketplace: str | None, query: str | None, limit: int) -> dict[str, Any]:
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        rows = fetch_rows(conn, marketplace, query, limit)
        return build_report(rows)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize latest stored prices from SQLite history.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--marketplace", help="Optional marketplace filter")
    parser.add_argument("--query", help="Optional exact query filter")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of products to include")
    args = parser.parse_args()

    print(json.dumps(load_report(args.db_path, args.marketplace, args.query, args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
