#!/usr/bin/env python3

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fetch_amazon_br import run as run_amazon
from fetch_mercadolivre_br import run as run_mercadolivre
from fetch_shopee_br import run as run_shopee


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
SCRIPT_DIR = Path(__file__).resolve().parent
AMAZON_FETCHER = SCRIPT_DIR / "fetch_amazon_br.py"
MERCADOLIVRE_FETCHER = SCRIPT_DIR / "fetch_mercadolivre_br.py"
SHOPEE_FETCHER = SCRIPT_DIR / "fetch_shopee_br.py"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            marketplace TEXT NOT NULL,
            external_id TEXT,
            canonical_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            image_url TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            captured_at TEXT NOT NULL,
            query TEXT NOT NULL,
            position INTEGER,
            price REAL,
            price_text TEXT,
            list_price REAL,
            list_price_text TEXT,
            rating REAL,
            rating_text TEXT,
            review_count INTEGER,
            is_sponsored INTEGER NOT NULL DEFAULT 0,
            availability TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_products_marketplace_key
        ON products(marketplace, canonical_key);

        CREATE INDEX IF NOT EXISTS idx_price_snapshots_product_captured
        ON price_snapshots(product_id, captured_at);

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
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_alert_events_product_reason
        ON alert_events(product_id, reason, created_at);

        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            query TEXT NOT NULL,
            target_price REAL,
            update_interval_minutes INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_run_at TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist_products (
            id INTEGER PRIMARY KEY,
            watchlist_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            marketplace TEXT NOT NULL,
            category TEXT,
            normalized_query TEXT,
            product_id INTEGER,
            zoom_url TEXT,
            session_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(watchlist_id, source_url),
            FOREIGN KEY(watchlist_id) REFERENCES watchlists(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS watchlist_runs (
            id INTEGER PRIMARY KEY,
            watchlist_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            details_json TEXT,
            FOREIGN KEY(watchlist_id) REFERENCES watchlists(id)
        );
        """
    )
    conn.commit()


def fetch_marketplace_results(
    marketplace: str,
    query: str,
    max_results: int,
    session_id: str | None,
) -> dict[str, Any]:
    if marketplace == "amazon_br":
        return run_amazon(query, "http://localhost:3000", "/v1/scrape", max_results, 30, 2500)
    elif marketplace == "mercadolivre_br":
        return run_mercadolivre(query, "http://localhost:3000", "/v1/scrape", max_results, 30, 2500)
    elif marketplace == "shopee_br":
        return run_shopee(query, "http://localhost:3000", "/v1/scrape", max_results, 30, 3000, session_id)
    else:
        raise ValueError(f"Unsupported marketplace: {marketplace}")


def canonical_key(marketplace: str, product: dict[str, Any]) -> str:
    external_id = product.get("asin")
    if external_id:
        return f"{marketplace}:{external_id}"
    return f"{marketplace}:url:{product['url']}"


def upsert_product(
    conn: sqlite3.Connection,
    marketplace: str,
    captured_at: str,
    product: dict[str, Any],
) -> int:
    key = canonical_key(marketplace, product)
    external_id = product.get("asin")
    row = conn.execute(
        "SELECT id FROM products WHERE canonical_key = ?",
        (key,),
    ).fetchone()

    if row:
        product_id = int(row[0])
        conn.execute(
            """
            UPDATE products
            SET title = ?, url = ?, image_url = ?, last_seen_at = ?
            WHERE id = ?
            """,
            (
                product["title"],
                product["url"],
                product.get("image_url"),
                captured_at,
                product_id,
            ),
        )
        return product_id

    cursor = conn.execute(
        """
        INSERT INTO products (
            marketplace, external_id, canonical_key, title, url, image_url, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            marketplace,
            external_id,
            key,
            product["title"],
            product["url"],
            product.get("image_url"),
            captured_at,
            captured_at,
        ),
    )
    return int(cursor.lastrowid)


def insert_snapshot(
    conn: sqlite3.Connection,
    product_id: int,
    query: str,
    captured_at: str,
    product: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO price_snapshots (
            product_id, captured_at, query, position, price, price_text, list_price, list_price_text,
            rating, rating_text, review_count, is_sponsored, availability
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            captured_at,
            query,
            product.get("position"),
            product.get("price"),
            product.get("price_text"),
            product.get("list_price"),
            product.get("list_price_text"),
            product.get("rating"),
            product.get("rating_text"),
            product.get("review_count"),
            1 if product.get("is_sponsored") else 0,
            product.get("availability"),
        ),
    )


def previous_stats(conn: sqlite3.Connection, product_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            MIN(CASE WHEN price IS NOT NULL THEN price END) AS min_price,
            SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) AS priced_snapshots
        FROM price_snapshots
        WHERE product_id = ?
        """,
        (product_id,),
    ).fetchone()
    return {
        "min_price": row[0] if row else None,
        "priced_snapshots": row[1] if row else 0,
    }


def build_alert_candidate(
    conn: sqlite3.Connection,
    product_id: int,
    product: dict[str, Any],
) -> dict[str, Any] | None:
    price = product.get("price")
    if price is None:
        return None

    stats = previous_stats(conn, product_id)
    min_price = stats["min_price"]
    priced_snapshots = stats["priced_snapshots"]
    if priced_snapshots < 2 or min_price is None or price != min_price:
        return None

    return {
        "product_id": product_id,
        "title": product["title"],
        "url": product["url"],
        "price": price,
        "price_text": product.get("price_text"),
        "reason": "lowest_recorded_price",
    }


def monitor_query(
    marketplace: str,
    query: str,
    db_path: Path,
    max_results: int,
    session_id: str | None,
) -> dict[str, Any]:
    fetched = fetch_marketplace_results(
        marketplace=marketplace,
        query=query,
        max_results=max_results,
        session_id=session_id,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    captured_at = fetched.get("captured_at") or datetime.now(timezone.utc).isoformat()
    stored_products = 0
    alert_candidates: list[dict[str, Any]] = []

    try:
        for product in fetched.get("products", []):
            if not product.get("title") or not product.get("url"):
                continue
            product_id = upsert_product(conn, marketplace, captured_at, product)
            insert_snapshot(conn, product_id, query, captured_at, product)
            stored_products += 1

        conn.commit()

        for product in fetched.get("products", []):
            if not product.get("title") or not product.get("url"):
                continue
            product_id = conn.execute(
                "SELECT id FROM products WHERE canonical_key = ?",
                (canonical_key(marketplace, product),),
            ).fetchone()[0]
            candidate = build_alert_candidate(conn, product_id, product)
            if candidate:
                alert_candidates.append(candidate)
    finally:
        conn.close()

    return {
        "marketplace": marketplace,
        "query": query,
        "captured_at": captured_at,
        "db_path": str(db_path),
        "stored_products": stored_products,
        "source_errors": fetched.get("errors", []),
        "alert_candidates": alert_candidates,
        "products": fetched.get("products", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a marketplace fetcher and store price history in SQLite.")
    parser.add_argument("marketplace", help="Marketplace key, e.g. amazon_br")
    parser.add_argument("query", help="Search query to monitor")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum products to fetch from the marketplace")
    parser.add_argument("--session-id", help="Optional Steel session id for marketplaces that require authenticated reuse")
    args = parser.parse_args()

    result = monitor_query(
        marketplace=args.marketplace,
        query=args.query,
        db_path=Path(args.db_path),
        max_results=args.max_results,
        session_id=args.session_id,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
