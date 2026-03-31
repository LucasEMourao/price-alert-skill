#!/usr/bin/env python3

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

from enrich_with_zoom import enrich_zoom_product
from run_all_monitors import run_all_monitors

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
DEFAULT_MARKETPLACES = ["amazon_br", "mercadolivre_br", "shopee_br"]
STOPWORDS = {"de", "da", "do", "e", "com", "para", "em", "o", "a", "os", "as", "na", "no"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            categories_json TEXT,
            query TEXT NOT NULL,
            queries_json TEXT,
            marketplaces_json TEXT,
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
            UNIQUE(watchlist_id, source_url)
        );
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(watchlists)").fetchall()}
    if "marketplaces_json" not in columns:
        conn.execute("ALTER TABLE watchlists ADD COLUMN marketplaces_json TEXT")
    if "categories_json" not in columns:
        conn.execute("ALTER TABLE watchlists ADD COLUMN categories_json TEXT")
    if "queries_json" not in columns:
        conn.execute("ALTER TABLE watchlists ADD COLUMN queries_json TEXT")
    conn.commit()


def detect_marketplace(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "amazon.com.br" in host:
        return "amazon_br"
    if "mercadolivre.com.br" in host or "meli.la" in host:
        return "mercadolivre_br"
    if "shopee.com.br" in host:
        return "shopee_br"
    raise ValueError(f"Unsupported marketplace URL: {url}")


def normalize_product_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    query_items = parse_qsl(parsed.query, keep_blank_values=False)
    kept_query = []
    if "amazon.com.br" in host:
        path_match = re.search(r"(/dp/[A-Z0-9]{10}|/gp/product/[A-Z0-9]{10})", path, re.IGNORECASE)
        if path_match:
            path = path_match.group(1)
    elif "mercadolivre.com.br" in host:
        path_match = re.search(r"(/p/MLB[A-Z0-9]+)", path, re.IGNORECASE)
        if path_match:
            path = path_match.group(1)
    elif "meli.la" in host:
        return url
    elif "shopee.com.br" in host and path.startswith("/search"):
        for key, value in query_items:
            if key == "keyword":
                kept_query.append((key, value))
    normalized_query = "&".join(f"{key}={value}" for key, value in kept_query)
    return urlunparse((parsed.scheme.lower() or "https", host, path or "/", "", normalized_query, ""))


def extract_external_id(marketplace: str, url: str) -> str | None:
    if marketplace == "amazon_br":
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url, re.IGNORECASE)
        return match.group(1).upper() if match else None
    if marketplace == "mercadolivre_br":
        match = re.search(r"/p/(MLB[A-Z0-9]+)", url, re.IGNORECASE)
        return match.group(1).upper() if match else None
    if marketplace == "shopee_br":
        match = re.search(r"-i\.(\d+)\.(\d+)", url, re.IGNORECASE)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
    return None


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def normalize_marketplaces(values: list[str] | None) -> list[str]:
    requested = values or DEFAULT_MARKETPLACES
    normalized = []
    for value in requested:
        if value in {"amazon_br", "mercadolivre_br", "shopee_br"} and value not in normalized:
            normalized.append(value)
    return normalized or DEFAULT_MARKETPLACES


def normalized_categories(payload: dict[str, Any]) -> list[str]:
    values = payload.get("categories")
    if values is None:
        values = [payload.get("category")] if payload.get("category") else []
    result = []
    for value in values:
        normalized = normalize_query(value or "")
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def infer_query_from_seed(seed: str, links: list[dict[str, Any]]) -> str:
    token_scores: dict[str, int] = {}
    for text in [seed] + [link.get("title") or "" for link in links] + [link.get("category") or "" for link in links]:
        for token in normalize_query(text).split():
            if not token or token in STOPWORDS:
                continue
            score = 1
            if any(char.isdigit() for char in token):
                score += 2
            if len(token) >= 5:
                score += 1
            token_scores[token] = token_scores.get(token, 0) + score

    ranked = sorted(token_scores.items(), key=lambda item: (-item[1], item[0]))
    query = " ".join(token for token, _ in ranked[:6]).strip()
    return query or "produto"


def infer_watchlist_queries(payload: dict[str, Any]) -> list[str]:
    explicit_queries = payload.get("queries") or []
    if payload.get("query"):
        explicit_queries = [payload["query"], *explicit_queries]

    normalized_explicit = []
    for query in explicit_queries:
        normalized = normalize_query(query or "")
        if normalized and normalized not in normalized_explicit:
            normalized_explicit.append(normalized)
    if normalized_explicit:
        return normalized_explicit

    categories = normalized_categories(payload)
    if categories:
        return categories

    links = payload.get("links") or []
    inferred = infer_query_from_seed("", links)
    return [inferred]


def infer_query(link: dict[str, Any], fallback_category: str | None) -> str:
    pieces = [link.get("title") or "", link.get("category") or "", fallback_category or ""]
    merged = " ".join(piece for piece in pieces if piece).strip()
    if not merged:
        return normalize_query(fallback_category or "") or "produto"
    tokens = [tok for tok in normalize_query(merged).split() if tok not in STOPWORDS]
    return " ".join(tokens[:10]) or normalize_query(fallback_category or "") or "produto"


def normalized_payload(payload: dict[str, Any]) -> dict[str, Any]:
    categories = normalized_categories(payload)
    links = payload.get("links") or []
    watch_queries = infer_watchlist_queries(payload)
    primary_query = watch_queries[0]
    primary_category = categories[0] if categories else None
    name = payload.get("name") or f"Monitorar {primary_category or primary_query}"
    return {
        **payload,
        "name": name,
        "category": primary_category,
        "categories": categories,
        "query": primary_query,
        "queries": watch_queries,
        "links": links,
        "marketplaces": normalize_marketplaces(payload.get("marketplaces")),
    }


def create_watchlist(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    ts = now_iso()
    cursor = conn.execute(
        """
        INSERT INTO watchlists (
            name, category, categories_json, query, queries_json, marketplaces_json, target_price, update_interval_minutes, active, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """,
        (
            payload["name"],
            payload.get("category"),
            json.dumps(payload.get("categories") or [], ensure_ascii=False),
            payload["query"],
            json.dumps(payload.get("queries") or [payload["query"]], ensure_ascii=False),
            json.dumps(payload.get("marketplaces") or DEFAULT_MARKETPLACES, ensure_ascii=False),
            payload.get("target_price"),
            payload["update_interval_minutes"],
            payload.get("notes"),
            ts,
            ts,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def add_watchlist_products(conn: sqlite3.Connection, watchlist_id: int, links: list[dict[str, Any]], category: str | None) -> list[dict[str, Any]]:
    ts = now_iso()
    rows = []
    for link in links:
        marketplace = detect_marketplace(link["url"])
        normalized = infer_query(link, category)
        conn.execute(
            """
            INSERT INTO watchlist_products (
                watchlist_id, source_url, marketplace, category, normalized_query, zoom_url, session_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                watchlist_id,
                link["url"],
                marketplace,
                link.get("category") or category,
                normalized,
                link.get("zoom_url"),
                link.get("session_id"),
                ts,
                ts,
            ),
        )
        rows.append(
            {
                "source_url": link["url"],
                "marketplace": marketplace,
                "normalized_query": normalized,
                "zoom_url": link.get("zoom_url"),
                "session_id": link.get("session_id"),
            }
        )
    conn.commit()
    return rows


def build_run_config(watchlist: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    if not products:
        return {
            "checks": [
                {
                    "query": query,
                    "marketplaces": watchlist.get("marketplaces") or DEFAULT_MARKETPLACES,
                    "max_results": 20,
                    "alert_limit": 20,
                }
                for query in (watchlist.get("queries") or [watchlist["query"]])
            ],
            "zoom_enrichments": [],
        }
    for product in products:
        query = product["normalized_query"] or watchlist["query"]
        entry = grouped.setdefault(
            query,
            {
                "query": query,
                "marketplaces": [],
                "max_results": 20,
                "alert_limit": 20,
                "session_ids": {},
            },
        )
        entry["marketplaces"].append(product["marketplace"])
        if product.get("session_id"):
            entry["session_ids"][product["marketplace"]] = product["session_id"]

    for entry in grouped.values():
        entry["marketplaces"] = sorted(set(entry["marketplaces"]))

    return {"checks": list(grouped.values()), "zoom_enrichments": []}


def hydrate_watchlist_product_ids(conn: sqlite3.Connection, watchlist_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, source_url, marketplace, zoom_url FROM watchlist_products WHERE watchlist_id = ?",
        (watchlist_id,),
    ).fetchall()
    enriched = []
    for row in rows:
        external_id = extract_external_id(row["marketplace"], row["source_url"])
        normalized_url = normalize_product_url(row["source_url"])
        product = None
        if external_id:
            product = conn.execute(
                "SELECT id FROM products WHERE marketplace = ? AND external_id = ? ORDER BY id DESC LIMIT 1",
                (row["marketplace"], external_id),
            ).fetchone()
        if not product:
            product = conn.execute(
                "SELECT id, url FROM products WHERE marketplace = ? ORDER BY id DESC",
                (row["marketplace"],),
            ).fetchall()
            for candidate in product:
                if normalize_product_url(candidate["url"]) == normalized_url:
                    product = candidate
                    break
            else:
                product = None
        product_id = int(product[0]) if product else None
        conn.execute(
            "UPDATE watchlist_products SET product_id = ?, updated_at = ? WHERE id = ?",
            (product_id, now_iso(), row["id"]),
        )
        enriched.append(
            {
                "watchlist_product_id": row["id"],
                "product_id": product_id,
                "zoom_url": row["zoom_url"],
            }
        )
    conn.commit()
    return enriched


def run_zoom_bootstrap(db_path: str, linked_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in linked_rows:
        if row.get("product_id") and row.get("zoom_url"):
            results.append(enrich_zoom_product(row["zoom_url"], row["product_id"], db_path))
    return results


def touch_watchlist_run(conn: sqlite3.Connection, watchlist_id: int) -> None:
    ts = now_iso()
    conn.execute(
        "UPDATE watchlists SET last_run_at = ?, updated_at = ? WHERE id = ?",
        (ts, ts, watchlist_id),
    )
    conn.commit()


def create_single_watchlist(payload: dict[str, Any], db_path: str, bootstrap: bool) -> dict[str, Any]:
    conn = sqlite3.connect(Path(db_path))
    try:
        ensure_schema(conn)
        watchlist_id = create_watchlist(conn, payload)
        product_rows = add_watchlist_products(conn, watchlist_id, payload.get("links", []), payload.get("category"))
    finally:
        conn.close()

    config = build_run_config(
        {
            "id": watchlist_id,
            "query": payload["query"],
            "queries": payload.get("queries"),
            "marketplaces": payload.get("marketplaces"),
        },
        product_rows,
    )

    bootstrap_result = None
    zoom_bootstrap = None
    if bootstrap:
        bootstrap_result = run_all_monitors(config, db_path, verbose=False)
        conn = sqlite3.connect(Path(db_path))
        conn.row_factory = sqlite3.Row
        try:
            linked_rows = hydrate_watchlist_product_ids(conn, watchlist_id)
            touch_watchlist_run(conn, watchlist_id)
        finally:
            conn.close()
        zoom_bootstrap = run_zoom_bootstrap(db_path, linked_rows)

    return {
        "watchlist_id": watchlist_id,
        "name": payload["name"],
        "inferred_query": payload["query"],
        "inferred_queries": payload.get("queries"),
        "categories": payload.get("categories"),
        "marketplaces": payload.get("marketplaces"),
        "config": config,
        "bootstrap_result": bootstrap_result,
        "zoom_bootstrap": zoom_bootstrap,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a watchlist from user-provided product links and bootstrap initial data.")
    parser.add_argument("input_path", help="Path to onboarding JSON")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--bootstrap", action="store_true", help="Run the initial population pass after creating the watchlist")
    args = parser.parse_args()

    raw_payload = json.loads(Path(args.input_path).read_text())
    raw_watchlists = raw_payload.get("watchlists")
    if raw_watchlists is None:
        raw_watchlists = [raw_payload]

    results = []
    for raw_watchlist in raw_watchlists:
        payload = normalized_payload(raw_watchlist)
        results.append(create_single_watchlist(payload, args.db_path, args.bootstrap))

    response = results[0] if len(results) == 1 else {"watchlists": results, "count": len(results)}
    print(json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    main()
