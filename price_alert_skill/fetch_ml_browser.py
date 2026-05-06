#!/usr/bin/env python3

"""Fetch Mercado Livre Brasil search result prices using Playwright.

Uses Playwright to render the ML search page with JavaScript and extract
product data from the rendered DOM via page.evaluate().
"""

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any

from price_alert_skill.fetch_mercadolivre_br import (
    compute_confidence,
    parse_brl_from_label,
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
delete navigator.__proto__.webdriver;
"""

_EXTRACT_JS = """
(() => {
  const wrappers = document.querySelectorAll('.ui-search-result__wrapper');
  const products = [];
  for (const w of wrappers) {
    const titleEl = w.querySelector('.poly-component__title, a.poly-component__title');
    if (!titleEl) continue;
    const title = titleEl.textContent.trim();
    if (!title || title.length < 3) continue;

    const productLink = w.querySelector('a[href*="mercadolivre.com.br/"][href*="/p/MLB"]');
    let url = productLink ? productLink.href : null;
    if (url && url.includes('#')) url = url.split('#')[0];

    const agoraEl = w.querySelector('[aria-label*="Agora"]');
    const currentPriceLabel = agoraEl ? agoraEl.getAttribute('aria-label') : null;

    const antesEl = w.querySelector('[aria-label*="Antes"]');
    const listPriceLabel = antesEl ? antesEl.getAttribute('aria-label') : null;

    const img = w.querySelector('img.poly-component__picture, img');
    const image = img ? img.src : null;

    const cardText = w.textContent;
    const mlbMatch = cardText.match(/MLB[A-Z]?\\d+/);
    const asin = mlbMatch ? mlbMatch[0] : null;

    const isSponsored = !!w.querySelector('[href*="click1.mercadolivre"], [href*="publicidade"]');

    products.push({
      title,
      url,
      currentPriceLabel,
      listPriceLabel,
      image,
      asin,
      isSponsored,
    });
  }
  return products;
})()
"""


def _extract_products_via_playwright(
    search_url: str,
    max_results: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        browser = p.chromium.launch(headless=True, args=launch_args)

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=_USER_AGENT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        context.add_init_script(_STEALTH_JS)
        page = context.new_page()
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        page.wait_for_timeout(3000)

        raw_products: list[dict[str, Any]] = page.evaluate(_EXTRACT_JS)

        context.close()
        browser.close()

    return raw_products[:max_results] if max_results else raw_products


def slugify_query(query: str) -> str:
    """Convert query to URL slug."""
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", query.lower())).strip("-")


def _parse_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_products):
        title = raw.get("title")
        if not title or len(title) < 3:
            continue

        current_price = parse_brl_from_label(raw.get("currentPriceLabel"))
        list_price = parse_brl_from_label(raw.get("listPriceLabel"))

        url = raw.get("url")
        image_url = raw.get("image")
        asin = raw.get("asin")

        if not asin and url:
            url_mlb = re.search(r"/p/(MLB\d+)", url)
            if url_mlb:
                asin = url_mlb.group(1)

        if not url and asin:
            mlb_clean = re.search(r"(MLB)(\d+)", asin)
            if mlb_clean:
                url = f"https://www.mercadolivre.com.br/p/{mlb_clean.group(1)}{mlb_clean.group(2)}"

        is_sponsored = bool(raw.get("isSponsored"))

        product = {
            "position": idx + 1,
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
        }
        product["extraction_confidence"] = compute_confidence(product)

        if product["title"] and product["url"]:
            products.append(product)

    return products


def run(
    query: str,
    max_results: int = 20,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    slug = slugify_query(query)
    search_url = f"https://lista.mercadolivre.com.br/{slug}"

    payload: dict[str, Any] = {
        "marketplace": "mercadolivre_br",
        "query": query,
        "search_url": search_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
        "fetcher": "playwright",
    }

    try:
        raw_products = _extract_products_via_playwright(search_url, max_results, timeout_seconds)
        payload["products"] = _parse_products(raw_products)

        if not payload["products"]:
            payload["errors"].append(
                "No Mercado Livre products extracted. "
                "The page may have anti-bot protection or the HTML structure changed."
            )
    except Exception as exc:
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Mercado Livre Brasil prices using Playwright."
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max-results", type=int, default=20, help="Max products to return")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")
    args = parser.parse_args()

    result = run(
        query=args.query,
        max_results=args.max_results,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
