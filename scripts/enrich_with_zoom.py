#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from fetch_zoom_history import build_summary, fetch_steel_payload

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
            raw_summary_json TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_external_price_history_product_source
        ON external_price_history(product_id, source, captured_at);

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
            UNIQUE(product_id, source),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """
    )
    conn.commit()


def fetch_zoom_summary(zoom_url: str) -> dict[str, Any]:
    payload = fetch_steel_payload(zoom_url, "http://localhost:3000", "/v1/scrape", 40, 2500)
    return build_summary(zoom_url, payload)


def store_zoom_summary(conn: sqlite3.Connection, product_id: int | None, summary: dict[str, Any]) -> int:
    cursor = conn.execute(
        """
        INSERT INTO external_price_history (
            product_id, source, source_product_id, source_url, captured_at, title, image_url, brand, model,
            current_best_price, current_best_price_text, low_offer_price, high_offer_price, offer_count,
            median_price, tip_description, tip_window_start, tip_window_end, tip_text,
            visible_history_ranges_json, raw_summary_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            summary.get("source"),
            summary.get("zoom_product_id"),
            summary.get("canonical_url") or summary.get("zoom_url"),
            summary.get("captured_at"),
            summary.get("title"),
            summary.get("image_url"),
            summary.get("brand"),
            summary.get("model"),
            summary.get("current_best_price"),
            summary.get("current_best_price_text"),
            summary.get("low_offer_price"),
            summary.get("high_offer_price"),
            summary.get("offer_count"),
            summary.get("median_price"),
            summary.get("tip_description"),
            summary.get("tip_window_start"),
            summary.get("tip_window_end"),
            summary.get("tip_text"),
            json.dumps(summary.get("visible_history_ranges", []), ensure_ascii=False),
            json.dumps(summary.get("raw_summary", {}), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def enrich_zoom_product(zoom_url: str, product_id: int | None, db_path: str) -> dict[str, Any]:
    summary = fetch_zoom_summary(zoom_url)
    conn = sqlite3.connect(Path(db_path))
    try:
        ensure_schema(conn)
        enrichment_id = store_zoom_summary(conn, product_id, summary)
    finally:
        conn.close()
    return {"enrichment_id": enrichment_id, "product_id": product_id, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Store Zoom enrichment for a tracked product.")
    parser.add_argument("zoom_url", help="Zoom product URL")
    parser.add_argument("--product-id", type=int, help="Optional local products.id to link this enrichment to")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    print(json.dumps(enrich_zoom_product(args.zoom_url, args.product_id, args.db_path), ensure_ascii=False))


if __name__ == "__main__":
    main()
