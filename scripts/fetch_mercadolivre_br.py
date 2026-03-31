#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


def parse_brl_amount(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"R\$\s*([\d\.\,]+)", text)
    if not match:
        return None
    normalized = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def first_brl_text(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"R\$\s*[\d\.]+(?:,\d{2})?", text)
    return match.group(0) if match else None


def compute_confidence(product: dict[str, Any]) -> float:
    score = 0.0
    if product.get("title"):
        score += 0.4
    if product.get("url"):
        score += 0.3
    if product.get("price") is not None:
        score += 0.3
    return round(score, 2)


class MercadoLivreSearchHTMLParser(HTMLParser):
    def __init__(self, max_results: int) -> None:
        super().__init__()
        self.max_results = max_results
        self.products: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.card_depth = 0
        self.current_field: str | None = None
        self.link_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = attr_map.get("class", "")

        if (
            tag == "li"
            and "ui-search-layout__item" in classes
            and len(self.products) < self.max_results
        ):
            self.current = {
                "position": len(self.products) + 1,
                "asin": attr_map.get("data-id"),
                "title": None,
                "url": None,
                "image_url": None,
                "price_text": None,
                "price": None,
                "list_price_text": None,
                "list_price": None,
                "rating_text": None,
                "rating": None,
                "review_count": None,
                "is_sponsored": False,
                "availability": "unknown",
                "_text_parts": [],
            }
            self.card_depth = 1
            self.current_field = None
            self.link_stack = []
            return

        if not self.current:
            return

        if tag == "li":
            self.card_depth += 1

        if tag == "a":
            href = attr_map.get("href", "")
            self.link_stack.append(href)
            if (
                self.current.get("url") is None
                and href.startswith("http")
                and "mercadolivre.com.br" in href
                and "click1.mercadolivre.com.br" not in href
            ):
                self.current["url"] = href
                self.current_field = "title"
            if "click1.mercadolivre.com.br" in href:
                self.current["is_sponsored"] = True

        if tag == "img" and self.current.get("image_url") is None:
            image = attr_map.get("data-src") or attr_map.get("src")
            if image and image.startswith("http"):
                self.current["image_url"] = image

    def handle_endtag(self, tag: str) -> None:
        if not self.current:
            return

        if tag == "li":
            self.card_depth -= 1
            if self.card_depth == 0:
                full_text = " ".join(self.current.pop("_text_parts", []))
                price_text = first_brl_text(full_text)
                if price_text:
                    self.current["price_text"] = price_text
                    self.current["price"] = parse_brl_amount(price_text)
                if not self.current.get("asin") and self.current.get("url"):
                    match = re.search(r"/(MLB[A-Z]?\d+)", self.current["url"])
                    if match:
                        self.current["asin"] = match.group(1)
                if self.current.get("title") and self.current.get("url"):
                    self.products.append(self.current)
                self.current = None
                self.current_field = None
                self.link_stack = []
                return

        if tag == "a":
            if self.link_stack:
                self.link_stack.pop()
            self.current_field = None

        if tag == "span":
            self.current_field = None

    def handle_data(self, data: str) -> None:
        if not self.current:
            return

        text = data.strip()
        if not text:
            return

        if "Patrocinado" in text:
            self.current["is_sponsored"] = True

        self.current["_text_parts"].append(text)

        if self.current_field == "title" and self.current.get("title") is None and len(text) > 3:
            self.current["title"] = text
            return


def fetch_html_via_steel(
    search_url: str,
    api_base: str,
    scrape_endpoint: str,
    timeout_seconds: int,
    delay_ms: int,
) -> str:
    payload = json.dumps({"url": search_url, "delay": delay_ms}).encode("utf-8")
    request = Request(
        url=f"{api_base.rstrip('/')}{scrape_endpoint}",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8")


def extract_html_from_response(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(parsed, dict):
        if isinstance(parsed.get("content"), dict):
            html = parsed["content"].get("html")
            if isinstance(html, str):
                return html
        html = parsed.get("html")
        if isinstance(html, str):
            return html
    return body


def normalize_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for raw in raw_products:
        product = {
            "position": raw["position"],
            "asin": raw.get("asin"),
            "title": raw.get("title"),
            "url": raw.get("url"),
            "image_url": raw.get("image_url"),
            "price_text": raw.get("price_text"),
            "price": parse_brl_amount(raw.get("price_text")),
            "list_price_text": None,
            "list_price": None,
            "rating_text": None,
            "rating": None,
            "review_count": None,
            "is_sponsored": bool(raw.get("is_sponsored")),
            "availability": raw.get("availability") or "unknown",
        }
        product["extraction_confidence"] = compute_confidence(product)
        if product["title"] and product["url"]:
            products.append(product)
    return products


def slugify_query(query: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", query.lower())).strip("-")


def run(
    query: str,
    api_base: str,
    scrape_endpoint: str,
    max_results: int,
    timeout_seconds: int,
    delay_ms: int,
) -> dict[str, Any]:
    search_url = f"https://lista.mercadolivre.com.br/{slugify_query(query)}"
    payload = {
        "marketplace": "mercadolivre_br",
        "query": query,
        "search_url": search_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
    }

    try:
        body = fetch_html_via_steel(search_url, api_base, scrape_endpoint, timeout_seconds, delay_ms)
        html = extract_html_from_response(body)
        parser = MercadoLivreSearchHTMLParser(max_results=max_results)
        parser.feed(html)
        payload["products"] = normalize_products(parser.products)
        if not payload["products"]:
            payload["errors"].append(
                "No Mercado Livre products extracted. Confirm the Steel scrape endpoint returns result-card HTML."
            )
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Mercado Livre Brasil search result prices via Steel API.")
    parser.add_argument("query", help="Search query to run against mercadolivre.com.br")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Steel API base URL")
    parser.add_argument("--scrape-endpoint", default="/v1/scrape", help="Steel scrape endpoint path")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum number of product cards to return")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout for the scrape request")
    parser.add_argument("--delay-ms", type=int, default=2500, help="Extra wait requested from Steel before capture")
    args = parser.parse_args()

    result = run(
        query=args.query,
        api_base=args.api_base,
        scrape_endpoint=args.scrape_endpoint,
        max_results=args.max_results,
        timeout_seconds=args.timeout_seconds,
        delay_ms=args.delay_ms,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
