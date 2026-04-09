#!/usr/bin/env python3

"""Fetch Mercado Livre Brasil search result prices.

Uses regex-based extraction on the HTML returned by the scrape server.
The ML page structure uses aria-labels for prices:
  - aria-label="Agora: X reais com Y centavos" for current price
  - aria-label="Antes: X reais" for original/strikethrough price
"""

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from config import ML_MATT_WORD, ML_MATT_TOOL


def parse_brl_from_label(text: str | None) -> float | None:
    """Parse price from ML aria-label like 'Agora: 206 reais com 64 centavos' or 'Antes: 299 reais'."""
    if not text:
        return None
    # Match patterns like "206 reais com 64 centavos" or "299 reais"
    match = re.search(r"([\d]+)\s*reais(?:\s*com\s*([\d]+)\s*centavos)?", text, re.IGNORECASE)
    if not match:
        return None
    reais = int(match.group(1))
    centavos = int(match.group(2)) if match.group(2) else 0
    return reais + centavos / 100


def compute_confidence(product: dict[str, Any]) -> float:
    score = 0.0
    if product.get("title"):
        score += 0.4
    if product.get("url"):
        score += 0.3
    if product.get("price") is not None:
        score += 0.3
    return round(score, 2)


def extract_products_from_html(html: str, max_results: int) -> list[dict[str, Any]]:
    """Extract products from ML search page using regex."""
    products = []

    # Split by product wrapper
    wrappers = list(re.finditer(r'ui-search-result__wrapper', html))

    for idx, wrapper_match in enumerate(wrappers):
        if len(products) >= max_results:
            break

        start = wrapper_match.start()
        end = wrappers[idx + 1].start() if idx + 1 < len(wrappers) else start + 4000
        card = html[start:end]

        # Title
        title_match = re.search(r'poly-component__title[^>]*>([^<]+)', card)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        if not title or len(title) < 3:
            continue

        # Current price from "Agora:" aria-label
        agora_match = re.search(r'aria-label="Agora:\s*([^"]+)"', card)
        current_price = parse_brl_from_label(agora_match.group(1)) if agora_match else None

        # Original price from "Antes:" aria-label
        antes_match = re.search(r'aria-label="Antes:\s*([^"]+)"', card)
        list_price = parse_brl_from_label(antes_match.group(1)) if antes_match else None

        # Image
        img_match = re.search(r'poly-component__picture[^>]*src="([^"]+)"', card)
        image_url = img_match.group(1) if img_match else None

        # Extract MLB ID from image URL or card content
        mlb_match = re.search(r'(MLB[A-Z]?\d+)', card)
        asin = mlb_match.group(1) if mlb_match else None

        # Construct real URL from MLB ID using /p/ format (produto.mercadolivre.com.br returns 404)
        url = None
        if asin:
            mlb_clean = re.search(r'(MLB\d+)', asin)
            if mlb_clean:
                url = f"https://www.mercadolivre.com.br/p/{mlb_clean.group(1)}"

        # Sponsored detection
        is_sponsored = 'is_advertising=true' in card or 'type=pad' in card

        products.append({
            "position": len(products) + 1,
            "asin": asin,
            "title": title,
            "url": url,
            "image_url": image_url,
            "price_text": f"R$ {current_price:.2f}".replace(".", ",") if current_price else None,
            "price": current_price,
            "list_price_text": f"R$ {list_price:.2f}".replace(".", ",") if list_price else None,
            "list_price": list_price,
            "rating_text": None,
            "rating": None,
            "review_count": None,
            "is_sponsored": is_sponsored,
            "availability": "unknown",
        })

    return products


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


def build_affiliate_url(url: str | None) -> str | None:
    if not url:
        return None
    if ML_MATT_WORD and ML_MATT_TOOL:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}matt_word={ML_MATT_WORD}&matt_tool={ML_MATT_TOOL}"
    return url


def normalize_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for raw in raw_products:
        product = {
            "position": raw["position"],
            "asin": raw.get("asin"),
            "title": raw.get("title"),
            "url": build_affiliate_url(raw.get("url")),
            "image_url": raw.get("image_url"),
            "price_text": raw.get("price_text"),
            "price": raw.get("price"),
            "list_price_text": raw.get("list_price_text"),
            "list_price": raw.get("list_price"),
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
        raw_products = extract_products_from_html(html, max_results)
        payload["products"] = normalize_products(raw_products)
        if not payload["products"]:
            payload["errors"].append(
                "No Mercado Livre products extracted. Confirm the scrape endpoint returns result-card HTML."
            )
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Mercado Livre Brasil search result prices.")
    parser.add_argument("query", help="Search query to run against mercadolivre.com.br")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Scrape API base URL")
    parser.add_argument("--scrape-endpoint", default="/v1/scrape", help="Scrape endpoint path")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum number of product cards to return")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout for the scrape request")
    parser.add_argument("--delay-ms", type=int, default=2500, help="Extra wait requested before capture")
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
