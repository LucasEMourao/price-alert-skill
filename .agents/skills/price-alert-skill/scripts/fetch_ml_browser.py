#!/usr/bin/env python3

"""Fetch Mercado Livre Brasil search result prices using agent-browser CLI.

This fetcher uses agent-browser (Rust CLI for browser automation) to render
the ML search page with JavaScript and extract real product URLs from the
rendered HTML. This fixes the issue where constructed MLB URLs are fragile
and often return 404.

Requirements:
  - agent-browser installed globally: npm install -g agent-browser
  - Chrome installed: agent-browser install

Usage:
  python3 fetch_ml_browser.py "mouse gamer"
  python3 fetch_ml_browser.py "teclado mecanico" --max-results 10
"""

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from config import ML_MATT_WORD, ML_MATT_TOOL
from fetch_mercadolivre_br import compute_confidence, parse_brl_from_label


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

# JavaScript executed in the browser to extract product data as JSON.
_EXTRACT_JS = r"""
(() => {
  const wrappers = document.querySelectorAll('.ui-search-result__wrapper');
  const products = [];
  for (const w of wrappers) {
    // Title
    const titleEl = w.querySelector('.poly-component__title, a.poly-component__title');
    if (!titleEl) continue;
    const title = titleEl.textContent.trim();
    if (!title || title.length < 3) continue;

    // Product URL (real link with slug + MLB ID)
    const productLink = w.querySelector('a[href*="mercadolivre.com.br/"][href*="/p/MLB"]');
    let url = productLink ? productLink.href : null;
    // Strip fragment (#polycard_client=...)
    if (url && url.includes('#')) url = url.split('#')[0];

    // Current price
    const agoraEl = w.querySelector('[aria-label*="Agora"]');
    const currentPriceLabel = agoraEl ? agoraEl.getAttribute('aria-label') : null;

    // List price (original/strikethrough)
    const antesEl = w.querySelector('[aria-label*="Antes"]');
    const listPriceLabel = antesEl ? antesEl.getAttribute('aria-label') : null;

    // Image
    const img = w.querySelector('img.poly-component__picture, img');
    const image = img ? img.src : null;

    // MLB ID from card content
    const cardText = w.textContent;
    const mlbMatch = cardText.match(/MLB[A-Z]?\d+/);
    const asin = mlbMatch ? mlbMatch[0] : null;

    // Sponsored detection
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
  return JSON.stringify(products);
})()
"""


def _run_agent_browser(*commands: str, timeout: int = 60) -> str:
    """Run one or more agent-browser commands and return stdout.

    Commands are chained with '&&' so the browser state persists.
    """
    full_cmd = " && ".join(commands)
    result = subprocess.run(
        ["sh", "-c", f"agent-browser {_format_flags()} {full_cmd}"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 and result.stderr:
        raise RuntimeError(f"agent-browser error: {result.stderr.strip()}")
    return result.stdout.strip()


def _format_flags() -> str:
    return f'--user-agent "{_USER_AGENT}"'


def _extract_products_via_browser(
    search_url: str,
    max_results: int,
    timeout: int,
) -> list[dict[str, Any]]:
    """Open ML search page in agent-browser, extract products, close browser."""

    # Build the JS eval command (properly escaped for shell)
    js_escaped = _EXTRACT_JS.replace("'", "'\\''")

    cmds = [
        f'open "{search_url}"',
        "wait --load networkidle",
        f"eval '{js_escaped}'",
        "close",
    ]

    full_cmd = " && ".join(f"agent-browser {_format_flags()} {c}" for c in cmds)

    result = subprocess.run(
        ["sh", "-c", full_cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    # The eval output is the last meaningful line
    stdout = result.stdout
    raw_products: list[dict[str, Any]] = []

    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("[") or line.startswith('"['):
            # May be JSON array or stringified JSON
            try:
                data = json.loads(line)
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, list):
                    raw_products = data
                    break
            except json.JSONDecodeError:
                continue

    return raw_products[:max_results] if max_results else raw_products


def slugify_query(query: str) -> str:
    """Convert query to URL slug (same as fetch_mercadolivre_br)."""
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", query.lower())).strip("-")


def build_affiliate_url(url: str | None) -> str | None:
    """Append ML affiliate parameters to a URL."""
    if not url:
        return None
    if ML_MATT_WORD and ML_MATT_TOOL:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}matt_word={ML_MATT_WORD}&matt_tool={ML_MATT_TOOL}"
    return url


def _parse_products(raw_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw extracted data into normalized product dicts."""
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

        # Extract MLB ID from URL if not found in card text
        if not asin and url:
            url_mlb = re.search(r"/p/(MLB\d+)", url)
            if url_mlb:
                asin = url_mlb.group(1)

        # If no real URL extracted, fall back to MLB construction
        if not url and asin:
            mlb_clean = re.search(r"(MLB)(\d+)", asin)
            if mlb_clean:
                url = f"https://www.mercadolivre.com.br/p/{mlb_clean.group(1)}{mlb_clean.group(2)}"

        is_sponsored = bool(raw.get("isSponsored"))

        product = {
            "position": idx + 1,
            "asin": asin,
            "title": title,
            "url": build_affiliate_url(url),
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
    """Fetch Mercado Livre products using agent-browser (JS-rendered page)."""
    slug = slugify_query(query)
    search_url = f"https://lista.mercadolivre.com.br/{slug}"

    payload: dict[str, Any] = {
        "marketplace": "mercadolivre_br",
        "query": query,
        "search_url": search_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
        "errors": [],
        "fetcher": "agent-browser",
    }

    try:
        raw_products = _extract_products_via_browser(search_url, max_results, timeout_seconds)
        payload["products"] = _parse_products(raw_products)

        if not payload["products"]:
            payload["errors"].append(
                "No products extracted via agent-browser. "
                "The page may have anti-bot protection or the HTML structure changed."
            )
    except subprocess.TimeoutExpired:
        payload["errors"].append(f"agent-browser timed out after {timeout_seconds}s")
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"{type(exc).__name__}: {exc}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Mercado Livre Brasil prices using agent-browser."
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
