#!/usr/bin/env python3

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enrich_with_zoom import enrich_zoom_product
from generate_alert_payloads import generate_payloads, MIN_RELEVANT_DISCOUNT_PCT
from link_zoom_product import link_best_zoom_product
from monitor_query import monitor_query


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
AUTO_ZOOM_THRESHOLD = 0.6
DEFAULT_SCRAPE_CONCURRENCY = 1
DEFAULT_ZOOM_CONCURRENCY = 1
ZOOM_ELIGIBLE_TOKENS = {
    "ssd",
    "hd",
    "nvme",
    "notebook",
    "laptop",
    "placa",
    "video",
    "gpu",
    "memoria",
    "ddr4",
    "ddr5",
    "monitor",
    "tv",
    "celular",
    "smartphone",
    "iphone",
    "galaxy",
    "fone",
    "headset",
    "teclado",
    "mouse",
    "console",
    "ps5",
    "xbox",
    "cafeteira",
    "espresso",
    "air",
    "fryer",
    "geladeira",
    "fogao",
    "microondas",
    "aspirador",
    "lavadora",
    "secadora",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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


def run_monitor(check: dict[str, Any], marketplace: str, db_path: str) -> dict[str, Any]:
    session_map = check.get("session_ids") or {}
    session_id = session_map.get(marketplace) or check.get("session_id")
    return monitor_query(
        marketplace,
        check["query"],
        Path(db_path),
        int(check.get("max_results", 20)),
        session_id,
    )


def run_zoom_enrichment(task: dict[str, Any], db_path: str) -> dict[str, Any]:
    if task.get("zoom_url"):
        return enrich_zoom_product(task["zoom_url"], task["product_id"], db_path)

    if task.get("auto_match"):
        link_result = link_best_zoom_product(
            task["product_id"],
            db_path,
            apply=True,
            threshold=float(task.get("threshold", 0.55)),
        )
        best = link_result.get("best_match")
        if best:
            enrich_result = enrich_zoom_product(best["url"], task["product_id"], db_path)
            return {"link_result": link_result, "enrich_result": enrich_result}
        return {"link_result": link_result, "enrich_result": None}

    raise ValueError("Zoom enrichment task requires either zoom_url or auto_match=true")


def normalize_tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in text).split()
        if token
    }


def load_product_context(conn: sqlite3.Connection, product_ids: list[int]) -> tuple[dict[int, int], dict[int, datetime]]:
    if not product_ids:
        return {}, {}
    placeholders = ",".join("?" for _ in product_ids)
    snapshot_rows = conn.execute(
        f"""
        SELECT product_id, COUNT(1) AS priced_snapshots
        FROM price_snapshots
        WHERE product_id IN ({placeholders}) AND price IS NOT NULL
        GROUP BY product_id
        """,
        product_ids,
    ).fetchall()
    zoom_rows = conn.execute(
        f"""
        SELECT product_id, MAX(captured_at) AS captured_at
        FROM external_price_history
        WHERE source = 'zoom_br' AND product_id IN ({placeholders})
        GROUP BY product_id
        """,
        product_ids,
    ).fetchall()
    snapshot_map = {int(row[0]): int(row[1]) for row in snapshot_rows}
    zoom_map = {int(row[0]): datetime.fromisoformat(row[1]) for row in zoom_rows if row[1]}
    return snapshot_map, zoom_map


def looks_zoom_eligible(payload: dict[str, Any]) -> bool:
    if payload.get("marketplace") == "shopee_br":
        return False
    combined = f"{payload.get('product_title', '')} {payload.get('query', '')}"
    return bool(normalize_tokens(combined) & ZOOM_ELIGIBLE_TOKENS)


def has_recent_zoom_baseline(captured_at: datetime | None) -> bool:
    if captured_at is None:
        return False
    age_days = (datetime.now(timezone.utc) - captured_at).total_seconds() / 86400
    return age_days <= 7


def auto_zoom_tasks(conn: sqlite3.Connection, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_ids = [payload["product_id"] for payload in payloads if payload.get("product_id") is not None]
    snapshot_map, zoom_map = load_product_context(conn, product_ids)
    tasks = []
    seen_products: set[int] = set()
    for payload in payloads:
        product_id = payload.get("product_id")
        if (
            product_id is None
            or product_id in seen_products
            or not looks_zoom_eligible(payload)
            or has_recent_zoom_baseline(zoom_map.get(product_id))
            or snapshot_map.get(product_id, 0) >= 2
        ):
            continue
        seen_products.add(product_id)
        tasks.append({"product_id": product_id, "auto_match": True, "threshold": AUTO_ZOOM_THRESHOLD})
    return tasks


def load_payloads(check: dict[str, Any], db_path: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for marketplace in check.get("marketplaces") or []:
        payloads.extend(
            generate_payloads(
                db_path,
                marketplace,
                check["query"],
                int(check.get("alert_limit", 20)),
                only_lowest=False,
                min_relevant_discount_pct=MIN_RELEVANT_DISCOUNT_PCT,
            )["items"]
        )
    return payloads


def fingerprint_for(payload: dict[str, Any]) -> str:
    reference = payload.get("previous_price_reference") or {}
    raw = json.dumps(
        {
            "product_id": payload["product_id"],
            "reason": payload.get("reason"),
            "current_price": payload.get("current_price"),
            "reference_kind": reference.get("kind"),
            "reference_price": reference.get("value"),
            "discount_pct": payload.get("discount_pct"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persist_new_alerts(conn: sqlite3.Connection, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    new_alerts = []
    now = datetime.now(timezone.utc).isoformat()
    for payload in payloads:
        if not payload.get("actionable") or not payload.get("reason"):
            continue
        fingerprint = fingerprint_for(payload)
        exists = conn.execute(
            "SELECT 1 FROM alert_events WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if exists:
            continue

        reference = payload.get("previous_price_reference") or {}
        conn.execute(
            """
            INSERT INTO alert_events (
                product_id, marketplace, query, reason, fingerprint, current_price, reference_price,
                discount_pct, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["product_id"],
                payload["marketplace"],
                payload["query"],
                payload["reason"],
                fingerprint,
                payload.get("current_price"),
                reference.get("value"),
                payload.get("discount_pct"),
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
        new_alerts.append(payload)

    conn.commit()
    return new_alerts


def run_all_monitors(config: dict[str, Any], db_path: str, verbose: bool = False) -> dict[str, Any]:
    checks = config.get("checks", [])
    zoom_tasks = config.get("zoom_enrichments", [])
    scrape_concurrency = max(1, int(config.get("scrape_concurrency", DEFAULT_SCRAPE_CONCURRENCY)))
    zoom_concurrency = max(1, int(config.get("zoom_concurrency", DEFAULT_ZOOM_CONCURRENCY)))

    monitor_results: list[dict[str, Any]] = []
    monitor_jobs = [
        (check, marketplace)
        for check in checks
        for marketplace in (check.get("marketplaces") or [])
    ]
    with ThreadPoolExecutor(max_workers=min(scrape_concurrency, max(1, len(monitor_jobs)))) as executor:
        futures = [executor.submit(run_monitor, check, marketplace, db_path) for check, marketplace in monitor_jobs]
        for future in as_completed(futures):
            monitor_results.append(future.result())

    zoom_results = []
    with ThreadPoolExecutor(max_workers=min(zoom_concurrency, max(1, len(zoom_tasks)))) as executor:
        futures = [executor.submit(run_zoom_enrichment, task, db_path) for task in zoom_tasks]
        for future in as_completed(futures):
            zoom_results.append(future.result())

    payloads: list[dict[str, Any]] = []
    for check in checks:
        payloads.extend(load_payloads(check, db_path))

    conn = sqlite3.connect(Path(db_path))
    try:
        ensure_schema(conn)
        implicit_zoom_tasks = auto_zoom_tasks(conn, payloads)
    finally:
        conn.close()

    if implicit_zoom_tasks:
        with ThreadPoolExecutor(max_workers=min(zoom_concurrency, max(1, len(implicit_zoom_tasks)))) as executor:
            futures = [executor.submit(run_zoom_enrichment, task, db_path) for task in implicit_zoom_tasks]
            for future in as_completed(futures):
                zoom_results.append(future.result())
        payloads = []
        for check in checks:
            payloads.extend(load_payloads(check, db_path))

    conn = sqlite3.connect(Path(db_path))
    try:
        ensure_schema(conn)
        new_alerts = persist_new_alerts(conn, payloads)
    finally:
        conn.close()

    response = {
        "watchlists_checked": len(checks),
        "scrape_concurrency": scrape_concurrency,
        "zoom_concurrency": zoom_concurrency,
        "zoom_task_count": len(zoom_tasks) + len(implicit_zoom_tasks),
        "payload_count": len(payloads),
        "new_alerts": new_alerts,
        "new_alert_count": len(new_alerts),
    }
    if verbose:
        response["monitor_results"] = monitor_results
        response["zoom_results"] = zoom_results
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all configured monitors, optional Zoom enrichment, and deduped alerts.")
    parser.add_argument("config_path", help="Path to JSON config file")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--verbose", action="store_true", help="Include full monitor and zoom details in stdout")
    args = parser.parse_args()

    config = json.loads(Path(args.config_path).read_text())
    print(json.dumps(run_all_monitors(config, args.db_path, verbose=args.verbose), ensure_ascii=False))


if __name__ == "__main__":
    main()
