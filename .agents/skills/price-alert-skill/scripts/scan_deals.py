#!/usr/bin/env python3

"""Scan marketplaces for products with displayed discounts and format WhatsApp messages.

This script does NOT use SQLite or historical data. It relies solely on the
discount information displayed by the marketplace itself (e.g., "de R$ 2.000 por R$ 1.500").
The responsibility for the accuracy of the discount lies with the marketplace.

Usage:
  python3 scan_deals.py "mouse gamer" --min-discount 10
  python3 scan_deals.py --all  # Scan all gamer categories
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fetch_amazon_br import run as run_amazon
from fetch_ml_browser import run as run_mercadolivre_browser
from generate_melila_links import generate_links
from utils import (
    calculate_discount,
    filter_new_deals,
    format_deal_message,
)

ROOT = Path(__file__).resolve().parents[1]
MESSAGES_DIR = ROOT / "data" / "messages"

GAMER_QUERIES = [
    "mouse gamer",
    "teclado mecanico gamer",
    "headset gamer",
    "monitor gamer",
    "ssd 2tb",
    "memoria ram ddr5",
    "placa de video rtx",
    "notebook gamer",
    "gabinete gamer",
    "fonte gamer",
    "cooler gamer",
    "mousepad gamer",
]


def extract_deals_from_products(
    products: list[dict[str, Any]],
    marketplace: str,
    query: str,
    min_discount: float,
) -> list[dict[str, Any]]:
    """Extract products that have a displayed discount >= min_discount."""
    deals = []
    for product in products:
        current_price = product.get("price")
        list_price = product.get("list_price")
        title = product.get("title", "")
        url = product.get("url", "")

        if not current_price or not title or not url:
            continue

        discount_pct = None
        previous_price = None

        if list_price and list_price > current_price:
            discount_pct = calculate_discount(current_price, list_price)
            previous_price = list_price

        if discount_pct is None or discount_pct < min_discount:
            continue

        deals.append({
            "title": title,
            "url": url,
            "image_url": product.get("image_url"),
            "marketplace": marketplace,
            "current_price": current_price,
            "current_price_text": product.get("price_text"),
            "previous_price": previous_price,
            "previous_price_text": product.get("list_price_text"),
            "discount_pct": discount_pct,
            "query": query,
        })

    return deals


def scan_marketplace(
    marketplace: str,
    query: str,
    api_base: str,
    max_results: int,
    min_discount: float,
) -> list[dict[str, Any]]:
    """Scan a single marketplace for deals."""
    if marketplace == "amazon_br":
        result = run_amazon(query, api_base, "/v1/scrape", max_results, 30, 2500)
    elif marketplace == "mercadolivre_br":
        result = run_mercadolivre_browser(query=query, max_results=max_results)
    else:
        return []

    products = result.get("products", [])
    return extract_deals_from_products(products, marketplace, query, min_discount)


def scan_all(
    api_base: str,
    max_results: int,
    min_discount: float,
    marketplaces: list[str],
    queries: list[str],
) -> list[dict[str, Any]]:
    """Scan multiple queries across marketplaces."""
    all_deals = []
    for query in queries:
        for marketplace in marketplaces:
            try:
                deals = scan_marketplace(marketplace, query, api_base, max_results, min_discount)
                if deals:
                    print(f"  ✓ {marketplace} / {query}: {len(deals)} deals found")
                all_deals.extend(deals)
            except Exception as exc:
                print(f"  ✗ {marketplace} / {query}: {exc}")
    return all_deals


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan marketplaces for products with displayed discounts.")
    parser.add_argument("query", nargs="?", help="Search query (omit if using --all)")
    parser.add_argument("--all", action="store_true", help="Scan all gamer categories")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Scrape server URL")
    parser.add_argument("--max-results", type=int, default=15, help="Max results per marketplace/query")
    parser.add_argument("--min-discount", type=float, default=10.0, help="Minimum discount %% to include")
    parser.add_argument("--marketplaces", default="amazon_br,mercadolivre_br", help="Comma-separated marketplaces")
    parser.add_argument("--no-melila", action="store_true", help="Skip meli.la link generation (use original URLs)")
    parser.add_argument("--output", help="Path to save messages JSON")
    args = parser.parse_args()

    if not args.query and not args.all:
        parser.error("Provide a query or use --all")

    marketplaces = [m.strip() for m in args.marketplaces.split(",")]
    queries = GAMER_QUERIES if args.all else [args.query]

    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Scanning for deals (min {args.min_discount}% off)...\n")

    deals = scan_all(args.api_base, args.max_results, args.min_discount, marketplaces, queries)

    # Deduplicate by URL (within this run)
    seen_urls = set()
    unique_deals = []
    for deal in deals:
        if deal["url"] not in seen_urls:
            seen_urls.add(deal["url"])
            unique_deals.append(deal)

    # Deduplicate against previously sent deals (cross-session)
    unique_deals, sent_data = filter_new_deals(unique_deals, auto_save=True)
    skipped = len(deals) - len(unique_deals)
    if skipped > 0:
        print(f"Skipped {skipped} already-sent deals")

    print(f"\nTotal new deals: {len(unique_deals)}")

    # Generate meli.la links for ML deals
    if not args.no_melila:
        ml_deals = [d for d in unique_deals if d["marketplace"] == "mercadolivre_br"]
        if ml_deals:
            ml_urls = [d["url"] for d in ml_deals]
            print(f"\nGenerating meli.la links for {len(ml_urls)} ML deals...")
            try:
                melila_map = generate_links(ml_urls)
                for deal in ml_deals:
                    deal["url"] = melila_map.get(deal["url"], deal["url"])
                generated = sum(1 for u in ml_urls if melila_map.get(u) and melila_map[u] != u)
                print(f"  Generated {generated}/{len(ml_urls)} meli.la links")
            except Exception as exc:
                print(f"  WARNING: meli.la generation failed: {exc}")
                print("  Falling back to original URLs")

    # Format messages
    messages = []
    for deal in unique_deals:
        message = format_deal_message(deal)
        messages.append({
            "title": deal["title"],
            "marketplace": deal["marketplace"],
            "current_price": deal["current_price"],
            "discount_pct": deal["discount_pct"],
            "url": deal["url"],
            "message": message,
        })

    # Save to file
    if messages:
        MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        output_path = args.output or str(MESSAGES_DIR / f"deals_{ts}.json")
        Path(output_path).write_text(json.dumps(
            {"messages": messages, "count": len(messages), "generated_at": now.isoformat()},
            ensure_ascii=False, indent=2,
        ))
        print(f"Saved to: {output_path}")

        # Print messages
        for msg in messages:
            print(f"\n{'='*50}")
            print(msg["message"])
            print(f"{'='*50}")
    else:
        print("No deals found matching criteria.")


if __name__ == "__main__":
    main()
