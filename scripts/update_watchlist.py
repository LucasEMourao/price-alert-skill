#!/usr/bin/env python3

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from run_all_monitors import run_all_monitors

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
RUNNER = Path(__file__).resolve().parent / "run_all_monitors.py"
DEFAULT_MARKETPLACES = ["amazon_br", "mercadolivre_br", "shopee_br"]


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

        CREATE TABLE IF NOT EXISTS watchlist_runs (
            id INTEGER PRIMARY KEY,
            watchlist_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            details_json TEXT
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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_due_watchlists(conn: sqlite3.Connection, watchlist_id: int | None) -> list[sqlite3.Row]:
    if watchlist_id is not None:
        return conn.execute("SELECT * FROM watchlists WHERE id = ? AND active = 1", (watchlist_id,)).fetchall()

    rows = conn.execute("SELECT * FROM watchlists WHERE active = 1").fetchall()
    due = []
    current = now_utc()
    for row in rows:
        last_run_at = row["last_run_at"]
        if not last_run_at:
            due.append(row)
            continue
        last = datetime.fromisoformat(last_run_at)
        if last + timedelta(minutes=row["update_interval_minutes"]) <= current:
            due.append(row)
    return due


def build_config(conn: sqlite3.Connection, watchlist: sqlite3.Row) -> dict[str, Any]:
    products = conn.execute(
        "SELECT * FROM watchlist_products WHERE watchlist_id = ?",
        (watchlist["id"],),
    ).fetchall()
    watchlist_marketplaces = json.loads(watchlist["marketplaces_json"]) if watchlist["marketplaces_json"] else DEFAULT_MARKETPLACES
    watchlist_queries = json.loads(watchlist["queries_json"]) if watchlist["queries_json"] else [watchlist["query"]]
    grouped: dict[str, dict[str, Any]] = {}
    zoom_tasks = []
    if not products:
        return {
            "checks": [
                {
                    "query": query,
                    "marketplaces": watchlist_marketplaces,
                    "max_results": 20,
                    "alert_limit": 20,
                }
                for query in watchlist_queries
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
        if product["session_id"]:
            entry["session_ids"][product["marketplace"]] = product["session_id"]
        if product["zoom_url"] and product["product_id"]:
            zoom_tasks.append({"product_id": product["product_id"], "zoom_url": product["zoom_url"]})

    for entry in grouped.values():
        entry["marketplaces"] = sorted(set(entry["marketplaces"]))
        if not entry["session_ids"]:
            entry.pop("session_ids")

    existing_queries = set(grouped)
    for query in watchlist_queries:
        if query in existing_queries:
            continue
        grouped[query] = {
            "query": query,
            "marketplaces": watchlist_marketplaces,
            "max_results": 20,
            "alert_limit": 20,
        }

    return {"checks": list(grouped.values()), "zoom_enrichments": zoom_tasks}


def insert_run(conn: sqlite3.Connection, watchlist_id: int) -> int:
    cursor = conn.execute(
        "INSERT INTO watchlist_runs (watchlist_id, started_at, status) VALUES (?, ?, ?)",
        (watchlist_id, now_utc().isoformat(), "running"),
    )
    conn.commit()
    return int(cursor.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, watchlist_id: int, status: str, details: dict[str, Any]) -> None:
    finished = now_utc().isoformat()
    conn.execute(
        "UPDATE watchlist_runs SET finished_at = ?, status = ?, details_json = ? WHERE id = ?",
        (finished, status, json.dumps(details, ensure_ascii=False), run_id),
    )
    if status == "success":
        conn.execute(
            "UPDATE watchlists SET last_run_at = ?, updated_at = ? WHERE id = ?",
            (finished, finished, watchlist_id),
        )
    conn.commit()


def run_config(config: dict[str, Any], db_path: str, watchlist_id: int) -> dict[str, Any]:
    return run_all_monitors(config, db_path, verbose=False)


def run_watchlist_updates(db_path: str, watchlist_id: int | None, force: bool) -> dict[str, Any]:
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    if force:
        if watchlist_id is not None:
            watchlists = conn.execute("SELECT * FROM watchlists WHERE id = ? AND active = 1", (watchlist_id,)).fetchall()
        else:
            watchlists = conn.execute("SELECT * FROM watchlists WHERE active = 1").fetchall()
    else:
        watchlists = load_due_watchlists(conn, watchlist_id)

    results = []
    for watchlist in watchlists:
        run_id = insert_run(conn, watchlist["id"])
        try:
            config = build_config(conn, watchlist)
            details = run_config(config, db_path, watchlist["id"])
            finish_run(conn, run_id, watchlist["id"], "success", details)
            results.append({"watchlist_id": watchlist["id"], "status": "success", "details": details})
        except Exception as exc:  # noqa: BLE001
            details = {"error": f"{type(exc).__name__}: {exc}"}
            finish_run(conn, run_id, watchlist["id"], "failed", details)
            results.append({"watchlist_id": watchlist["id"], "status": "failed", "details": details})

    conn.close()
    return {"watchlists_run": len(results), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run due watchlists based on user-defined update intervals.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--watchlist-id", type=int, help="Optional single watchlist id")
    parser.add_argument("--force", action="store_true", help="Run the selected watchlists even if they are not due yet")
    args = parser.parse_args()

    print(json.dumps(run_watchlist_updates(args.db_path, args.watchlist_id, args.force), ensure_ascii=False))


if __name__ == "__main__":
    main()
