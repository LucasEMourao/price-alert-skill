#!/usr/bin/env python3

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "price_history.sqlite3"
ZOOM_BASE = "https://www.zoom.com.br"
STOPWORDS = {
    "de",
    "da",
    "do",
    "e",
    "com",
    "para",
    "em",
    "no",
    "na",
    "o",
    "a",
    "os",
    "as",
    "por",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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
        """
    )
    conn.commit()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def tokens(text: str) -> set[str]:
    return {tok for tok in normalize(text).split() if tok and tok not in STOPWORDS}


def build_search_query(title: str) -> str:
    base_tokens = [tok for tok in normalize(title).split() if tok not in STOPWORDS]
    return " ".join(base_tokens[:10]) or title


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def jaccard(a: str, b: str) -> float:
    ta = tokens(a)
    tb = tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def score_candidate(product_title: str, candidate_title: str, product_url: str, candidate_url: str) -> float:
    seq = similarity(product_title, candidate_title)
    jac = jaccard(product_title, candidate_title)
    score = (seq * 0.6) + (jac * 0.4)
    if any(tok in normalize(candidate_title) for tok in tokens(product_title) if tok.isdigit()):
        score += 0.05
    if "samsung" in normalize(product_title) and "samsung" in normalize(candidate_title):
        score += 0.05
    if "amazon" in product_url and "amazon" in candidate_title.lower():
        score += 0.03
    size_tokens = {"1tb", "2tb", "4tb", "500gb", "250gb"}
    product_sizes = tokens(product_title) & size_tokens
    candidate_sizes = tokens(candidate_title) & size_tokens
    if product_sizes and candidate_sizes and product_sizes != candidate_sizes:
        score -= 0.12
    return round(min(score, 1.0), 4)


class ZoomSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_href: str | None = None
        self.current_text_parts: list[str] = []
        self.candidates: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if href.startswith("/"):
            self.current_href = href
            self.current_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.current_href:
            return
        title = " ".join(self.current_text_parts).strip()
        if (
            title
            and len(title) > 20
            and "/busca/" not in self.current_href
            and "/lead?" not in self.current_href
            and "cashback" not in title.lower()
            and "ver mais lojas" not in title.lower()
        ):
            self.candidates.append({"url": f"{ZOOM_BASE}{self.current_href}", "title": title})
        self.current_href = None
        self.current_text_parts = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            text = data.strip()
            if text:
                self.current_text_parts.append(text)


def fetch_zoom_search(search_query: str, api_base: str, delay_ms: int) -> str:
    url = f"{ZOOM_BASE}/search?q={quote_plus(search_query)}"
    payload = json.dumps({"url": url, "delay": delay_ms}).encode("utf-8")
    request = Request(
        url=f"{api_base.rstrip('/')}/v1/scrape",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=40) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8")).get("content", {}).get("html", "")


def get_product(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, marketplace, title, url FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown product_id: {product_id}")
    return row


def persist_link(conn: sqlite3.Connection, product_id: int, candidate: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    source_product_id = None
    match = re.search(r"/p/(MLB[A-Z]?\d+|\d+)", candidate["url"])
    if match:
        source_product_id = match.group(1)
    conn.execute(
        """
        INSERT INTO product_external_links (
            product_id, source, source_product_id, source_url, matched_title, score, created_at, updated_at
        ) VALUES (?, 'zoom_br', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id, source) DO UPDATE SET
            source_product_id = excluded.source_product_id,
            source_url = excluded.source_url,
            matched_title = excluded.matched_title,
            score = excluded.score,
            updated_at = excluded.updated_at
        """,
        (
            product_id,
            source_product_id,
            candidate["url"],
            candidate["title"],
            candidate["score"],
            now,
            now,
        ),
    )
    conn.commit()


def link_best_zoom_product(
    product_id: int,
    db_path: str,
    api_base: str = "http://localhost:3000",
    delay_ms: int = 2000,
    apply: bool = False,
    threshold: float = 0.55,
) -> dict[str, Any]:
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        product = get_product(conn, product_id)
        search_query = build_search_query(product["title"])
        html = fetch_zoom_search(search_query, api_base, delay_ms)
        parser_obj = ZoomSearchParser()
        parser_obj.feed(html)

        deduped: dict[str, dict[str, Any]] = {}
        for candidate in parser_obj.candidates:
            if candidate["url"] not in deduped:
                deduped[candidate["url"]] = candidate

        ranked = []
        for candidate in deduped.values():
            score = score_candidate(product["title"], candidate["title"], product["url"], candidate["url"])
            ranked.append({**candidate, "score": score})
        ranked.sort(key=lambda item: item["score"], reverse=True)
        best = ranked[0] if ranked else None

        if apply and best and best["score"] >= threshold:
            persist_link(conn, product_id, best)
    finally:
        conn.close()

    return {
        "product_id": product_id,
        "search_query": search_query,
        "best_match": best,
        "candidates": ranked[:10],
        "applied": bool(apply and best and best["score"] >= threshold),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Link a tracked retailer product to the best matching Zoom URL.")
    parser.add_argument("--product-id", type=int, required=True, help="Local products.id")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Steel API base URL")
    parser.add_argument("--delay-ms", type=int, default=2000, help="Extra wait requested from Steel before capture")
    parser.add_argument("--apply", action="store_true", help="Persist the best match into product_external_links")
    parser.add_argument("--threshold", type=float, default=0.55, help="Minimum score to persist when --apply is used")
    args = parser.parse_args()

    print(json.dumps(link_best_zoom_product(args.product_id, args.db_path, args.api_base, args.delay_ms, args.apply, args.threshold), ensure_ascii=False))


if __name__ == "__main__":
    main()
