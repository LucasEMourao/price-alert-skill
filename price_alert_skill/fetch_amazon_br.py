#!/usr/bin/env python3

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus

from price_alert_skill.config import AMAZON_AFFILIATE_TAG


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
                    # First price is the current price
                    self.current["price_text"] = self.current_price_candidates[0]
                    # If there's a second price higher than the first, it's the list price (original)
                    if len(self.current_price_candidates) > 1:
                        current_p = parse_brl_amount(self.current_price_candidates[0])
                        for candidate in self.current_price_candidates[1:]:
                            candidate_p = parse_brl_amount(candidate)
                            if candidate_p and current_p and candidate_p > current_p:
                                self.current["list_price_text"] = candidate
                                break

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


_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
delete navigator.__proto__.webdriver;
"""


def _fetch_html_playwright(search_url: str, delay_ms: int, timeout_seconds: int) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        context.add_init_script(_STEALTH_JS)
        page = context.new_page()
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        if delay_ms > 0:
            page.wait_for_timeout(delay_ms)
        html = page.content()
        context.close()
        browser.close()
    return html


def build_affiliate_url(asin: str | None, raw_url: str | None) -> str | None:
    if asin and AMAZON_AFFILIATE_TAG:
        return f"https://www.amazon.com.br/dp/{asin}?tag={AMAZON_AFFILIATE_TAG}"
    if raw_url and AMAZON_AFFILIATE_TAG:
        asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", raw_url)
        if asin_match:
            return f"https://www.amazon.com.br/dp/{asin_match.group(1)}?tag={AMAZON_AFFILIATE_TAG}"
    if raw_url:
        return raw_url
    return None


def normalize_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for raw in raw_products:
        product = {
            "position": raw["position"],
            "asin": raw.get("asin"),
            "title": raw.get("title"),
            "url": build_affiliate_url(raw.get("asin"), raw.get("url")),
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
    max_results: int = 20,
    timeout_seconds: int = 30,
    delay_ms: int = 3000,
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
        html = _fetch_html_playwright(search_url, delay_ms, timeout_seconds)
        parser = AmazonSearchHTMLParser(max_results=max_results)
        parser.feed(html)
        payload["products"] = normalize_products(parser.products)
        if not payload["products"]:
            payload["errors"].append(
                "No Amazon products extracted. The page may have anti-bot protection or the HTML structure changed."
            )
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Amazon Brasil search result prices via Playwright.")
    parser.add_argument("query", help="Search query to run against amazon.com.br")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum number of product cards to return")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Page load timeout in seconds")
    parser.add_argument("--delay-ms", type=int, default=3000, help="Extra wait before capturing HTML (ms)")
    args = parser.parse_args()

    result = run(
        query=args.query,
        max_results=args.max_results,
        timeout_seconds=args.timeout_seconds,
        delay_ms=args.delay_ms,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
