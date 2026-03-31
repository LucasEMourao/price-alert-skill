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


class ShopeeSearchHTMLParser(HTMLParser):
    def __init__(self, max_results: int) -> None:
        super().__init__()
        self.max_results = max_results
        self.products: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.anchor_depth = 0
        self.capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)

        if tag == "a" and len(self.products) < self.max_results:
            href = attr_map.get("href", "")
            if "/product/" in href or "-i." in href:
                url = href if href.startswith("http") else f"https://shopee.com.br{href}"
                self.current = {
                    "position": len(self.products) + 1,
                    "asin": extract_shopee_id(url),
                    "title": None,
                    "url": url,
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
                self.anchor_depth = 1
                self.capture_title = True
                return

        if not self.current:
            return

        if tag == "a":
            self.anchor_depth += 1

        if tag == "img" and self.current.get("image_url") is None:
            image = attr_map.get("src") or attr_map.get("data-src")
            if image and image.startswith("http"):
                self.current["image_url"] = image

    def handle_endtag(self, tag: str) -> None:
        if not self.current:
            return

        if tag == "a":
            self.anchor_depth -= 1
            if self.anchor_depth == 0:
                full_text = " ".join(self.current.pop("_text_parts", []))
                price_text = first_brl_text(full_text)
                if price_text:
                    self.current["price_text"] = price_text
                    self.current["price"] = parse_brl_amount(price_text)
                if self.current.get("title") and self.current.get("url"):
                    self.products.append(self.current)
                self.current = None
                self.capture_title = False

    def handle_data(self, data: str) -> None:
        if not self.current:
            return

        text = data.strip()
        if not text:
            return

        self.current["_text_parts"].append(text)
        if self.capture_title and self.current.get("title") is None and not text.startswith("R$") and len(text) > 3:
            self.current["title"] = text


def extract_shopee_id(url: str) -> str | None:
    match = re.search(r"-i\.(\d+\.\d+)$", url)
    if match:
        return match.group(1)
    match = re.search(r"/product/(\d+)/(\d+)", url)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None


def load_session_context(api_base: str, session_id: str) -> dict[str, Any]:
    with urlopen(f"{api_base.rstrip('/')}/v1/sessions/{session_id}/context", timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def fetch_html_via_steel(
    search_url: str,
    api_base: str,
    scrape_endpoint: str,
    timeout_seconds: int,
    delay_ms: int,
    session_context: dict[str, Any] | None,
) -> str:
    payload_dict: dict[str, Any] = {"url": search_url, "delay": delay_ms}
    if session_context:
        payload_dict["sessionContext"] = session_context
    payload = json.dumps(payload_dict).encode("utf-8")
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


def parse_metadata(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        metadata = parsed.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    return {}


def normalize_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_products:
        url = raw.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        product = {
            "position": raw["position"],
            "asin": raw.get("asin"),
            "title": raw.get("title"),
            "url": url,
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


def run(
    query: str,
    api_base: str,
    scrape_endpoint: str,
    max_results: int,
    timeout_seconds: int,
    delay_ms: int,
    session_id: str | None,
) -> dict[str, Any]:
    search_url = f"https://shopee.com.br/search?keyword={quote_plus(query)}"
    payload = {
        "marketplace": "shopee_br",
        "query": query,
        "search_url": search_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
    }

    try:
        session_context = load_session_context(api_base, session_id) if session_id else None
        body = fetch_html_via_steel(
            search_url,
            api_base,
            scrape_endpoint,
            timeout_seconds,
            delay_ms,
            session_context,
        )
        metadata = parse_metadata(body)
        url_source = str(metadata.get("urlSource", ""))
        title = str(metadata.get("title", ""))
        if "/buyer/login" in url_source or "Faça Login" in title:
            payload["errors"].append(
                "Shopee redirected the scrape to a login page. Create or reuse a logged-in Steel session and pass --session-id."
            )
            return payload
        html = extract_html_from_response(body)
        parser = ShopeeSearchHTMLParser(max_results=max_results)
        parser.feed(html)
        payload["products"] = normalize_products(parser.products)
        if not payload["products"]:
            if session_id:
                payload["errors"].append(
                    "No Shopee products extracted from the authenticated flow. The session may not be logged in yet, or Shopee returned a non-listing shell."
                )
            else:
                payload["errors"].append(
                    "No Shopee products extracted. The scrape may have returned an interstitial or non-listing shell."
                )
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Shopee Brasil search result prices via Steel API.")
    parser.add_argument("query", help="Search query to run against shopee.com.br")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Steel API base URL")
    parser.add_argument("--scrape-endpoint", default="/v1/scrape", help="Steel scrape endpoint path")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum number of product cards to return")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout for the scrape request")
    parser.add_argument("--delay-ms", type=int, default=3000, help="Extra wait requested from Steel before capture")
    parser.add_argument("--session-id", help="Optional Steel session id to reuse Shopee login cookies")
    args = parser.parse_args()

    result = run(
        query=args.query,
        api_base=args.api_base,
        scrape_endpoint=args.scrape_endpoint,
        max_results=args.max_results,
        timeout_seconds=args.timeout_seconds,
        delay_ms=args.delay_ms,
        session_id=args.session_id,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
