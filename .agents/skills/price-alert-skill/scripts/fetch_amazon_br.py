#!/usr/bin/env python3

import argparse
import json
import re
import sys
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


def parse_rating(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+[\,\.]?\d*)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_review_count(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d[\d\.\,]*)", text)
    if not match:
        return None
    normalized = match.group(1).replace(".", "").replace(",", "")
    try:
        return int(normalized)
    except ValueError:
        return None


def compute_confidence(product: dict[str, Any]) -> float:
    score = 0.0
    if product.get("title"):
        score += 0.35
    if product.get("url"):
        score += 0.25
    if product.get("price") is not None:
        score += 0.3
    if product.get("asin"):
        score += 0.1
    return round(score, 2)


class AmazonSearchHTMLParser(HTMLParser):
    def __init__(self, max_results: int) -> None:
        super().__init__()
        self.max_results = max_results
        self.products: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.current_field: str | None = None
        self.card_depth = 0
        self.current_price_candidates: list[str] = []
        self.anchor_stack: list[str] = []
        self.title_link_active = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if (
            tag == "div"
            and attr_map.get("data-component-type") == "s-search-result"
            and attr_map.get("data-asin")
            and len(self.products) < self.max_results
        ):
            self.current = {
                "position": len(self.products) + 1,
                "asin": attr_map.get("data-asin"),
                "title": None,
                "url": None,
                "image_url": None,
                "price_text": None,
                "list_price_text": None,
                "rating_text": None,
                "review_count_text": None,
                "is_sponsored": False,
                "availability": "unknown",
            }
            self.card_depth = 1
            self.current_price_candidates = []
            self.anchor_stack = []
            self.title_link_active = False
            return

        if not self.current:
            return

        if tag == "div":
            self.card_depth += 1

        classes = attr_map.get("class", "")

        if tag == "a":
            href = attr_map.get("href", "")
            self.anchor_stack.append(href)
            if self.current.get("url") is None and href.startswith("/"):
                self.current["url"] = f"https://www.amazon.com.br{href}"
            self.title_link_active = bool(re.search(r"/(?:sspa/)?dp/|/gp/product/", href))
            if "#customerReviews" in href:
                self.current_field = "review_count"

        if tag == "img" and "s-image" in classes and self.current.get("image_url") is None:
            self.current["image_url"] = attr_map.get("src")

        if tag == "span":
            if "a-offscreen" in classes:
                self.current_field = "price"

        if tag == "span" and attr_map.get("aria-label") and "de 5 estrelas" in attr_map["aria-label"]:
            self.current["rating_text"] = attr_map["aria-label"]

    def handle_endtag(self, tag: str) -> None:
        if not self.current:
            return

        if tag == "div":
            self.card_depth -= 1
            if self.card_depth == 0:
                if self.current_price_candidates:
                    self.current["price_text"] = self.current_price_candidates[0]

                if self.current.get("title") and self.current.get("url"):
                    self.products.append(self.current)

                self.current = None
                self.current_field = None
                self.current_price_candidates = []
                self.anchor_stack = []
                self.title_link_active = False
                return

        if tag == "span":
            self.current_field = None

        if tag == "a":
            if self.anchor_stack:
                self.anchor_stack.pop()
            self.title_link_active = False
            self.current_field = None

    def handle_data(self, data: str) -> None:
        if not self.current:
            return

        text = data.strip()
        if not text:
            return

        if "Patrocinado" in text:
            self.current["is_sponsored"] = True

        if self.current_field == "price" and text.startswith("R$"):
            self.current_price_candidates.append(text)
            return

        if self.title_link_active and self.current.get("title") is None and len(text) > 8 and not text.startswith("R$"):
            self.current["title"] = text
            return

        if self.current_field == "review_count" and self.current.get("review_count_text") is None:
            self.current["review_count_text"] = text


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
        body = response.read().decode("utf-8")
    return body


def extract_html_from_response(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(parsed, dict):
        for key in ("html", "markdown"):
            value = parsed.get(key)
            if isinstance(value, str) and "<" in value:
                return value
        if isinstance(parsed.get("content"), dict):
            content = parsed["content"]
            for key in ("html", "markdown", "content"):
                value = content.get(key)
                if isinstance(value, str) and "<" in value:
                    return value
        if isinstance(parsed.get("data"), dict):
            nested = parsed["data"]
            for key in ("html", "content"):
                value = nested.get(key)
                if isinstance(value, str) and "<" in value:
                    return value
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
            "list_price_text": raw.get("list_price_text"),
            "list_price": parse_brl_amount(raw.get("list_price_text")),
            "rating_text": raw.get("rating_text"),
            "rating": parse_rating(raw.get("rating_text")),
            "review_count": parse_review_count(raw.get("review_count_text")),
            "is_sponsored": bool(raw.get("is_sponsored")),
            "availability": raw.get("availability") or "unknown",
        }
        product["extraction_confidence"] = compute_confidence(product)
        if product["title"] and product["url"]:
            products.append(product)
    return products


def run(
    query: str,
    api_base: str,
    scrape_endpoint: str,
    max_results: int,
    timeout_seconds: int,
    delay_ms: int,
) -> dict[str, Any]:
    search_url = f"https://www.amazon.com.br/s?k={quote_plus(query)}"
    payload = {
        "marketplace": "amazon_br",
        "query": query,
        "search_url": search_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
    }

    try:
        body = fetch_html_via_steel(
            search_url=search_url,
            api_base=api_base,
            scrape_endpoint=scrape_endpoint,
            timeout_seconds=timeout_seconds,
            delay_ms=delay_ms,
        )
        html = extract_html_from_response(body)
        parser = AmazonSearchHTMLParser(max_results=max_results)
        parser.feed(html)
        payload["products"] = normalize_products(parser.products)
        if not payload["products"]:
            payload["errors"].append(
                "No Amazon products extracted. Confirm the Steel scrape endpoint returns HTML for the requested URL."
            )
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Amazon Brasil search result prices via Steel API.")
    parser.add_argument("query", help="Search query to run against amazon.com.br")
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
    sys.exit(main())
