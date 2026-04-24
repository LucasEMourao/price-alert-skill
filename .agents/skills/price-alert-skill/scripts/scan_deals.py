#!/usr/bin/env python3

"""Scan marketplaces for discounted products and prepare/send deal messages."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import configure_utf8_stdio, resolve_whatsapp_group
from deal_queue import (
    enqueue_or_update_normal,
    enqueue_urgent_retry,
    load_deal_queue,
    mark_scan_run,
    save_deal_queue,
)
from deal_selection import get_queries, prepare_deal_for_selection, qualifies_normal
from fetch_amazon_br import run as run_amazon
from fetch_ml_browser import run as run_mercadolivre_browser
from generate_melila_links import generate_links
from utils import (
    calculate_discount,
    can_send_again,
    filter_new_deals,
    format_deal_message,
    load_sent_deals,
    mark_deals_as_sent,
)

ROOT = Path(__file__).resolve().parents[1]
MESSAGES_DIR = ROOT / "data" / "messages"


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

        deals.append(
            {
                "title": title,
                "url": url,
                "product_url": url,
                "dedup_key": url,
                "image_url": product.get("image_url"),
                "marketplace": marketplace,
                "current_price": current_price,
                "current_price_text": product.get("price_text"),
                "previous_price": previous_price,
                "previous_price_text": product.get("list_price_text"),
                "discount_pct": discount_pct,
                "query": query,
                "source_query": query,
            }
        )

    return deals


def scan_marketplace(
    marketplace: str,
    query: str,
    max_results: int,
    min_discount: float,
) -> list[dict[str, Any]]:
    """Scan a single marketplace for deals."""
    if marketplace == "amazon_br":
        result = run_amazon(query=query, max_results=max_results)
    elif marketplace == "mercadolivre_br":
        result = run_mercadolivre_browser(query=query, max_results=max_results)
    else:
        return []

    products = result.get("products", [])
    return extract_deals_from_products(products, marketplace, query, min_discount)


def scan_all(
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
                deals = scan_marketplace(marketplace, query, max_results, min_discount)
                if deals:
                    print(f"  ✓ {marketplace} / {query}: {len(deals)} deals found")
                all_deals.extend(deals)
            except Exception as exc:
                print(f"  ✗ {marketplace} / {query}: {exc}")
    return all_deals


def deduplicate_run_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate deals within the same scan run by product URL."""
    seen_urls: set[str] = set()
    unique_deals = []
    for deal in deals:
        product_url = deal.get("product_url") or deal.get("url")
        if product_url not in seen_urls:
            seen_urls.add(product_url)
            unique_deals.append(deal)
    return unique_deals


def apply_affiliate_links(deals: list[dict[str, Any]]) -> None:
    """Replace Mercado Livre URLs with generated affiliate links when possible."""
    ml_deals = [deal for deal in deals if deal["marketplace"] == "mercadolivre_br"]
    if not ml_deals:
        return

    ml_urls = [deal["product_url"] for deal in ml_deals]
    print(f"\nGenerating meli.la links for {len(ml_urls)} ML deals...")
    try:
        melila_map = generate_links(ml_urls)
        for deal in ml_deals:
            product_url = deal["product_url"]
            affiliate_url = melila_map.get(product_url, product_url)
            deal["affiliate_url"] = affiliate_url
            deal["url"] = affiliate_url
        generated = sum(
            1
            for url in ml_urls
            if melila_map.get(url) and melila_map[url] != url
        )
        print(f"  Generated {generated}/{len(ml_urls)} meli.la links")
    except Exception as exc:
        print(f"  WARNING: meli.la generation failed: {exc}")
        print("  Falling back to original URLs")
        for deal in ml_deals:
            deal["affiliate_url"] = deal["product_url"]


def build_messages_payload(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build printable/savable message payloads from normalized deals."""
    messages = []
    for deal in deals:
        message = format_deal_message(deal)
        deal["message"] = message
        deal["dedup_key"] = deal.get("dedup_key") or deal.get("offer_key") or deal["url"]
        messages.append(
            {
                "title": deal["title"],
                "marketplace": deal["marketplace"],
                "current_price": deal["current_price"],
                "discount_pct": deal["discount_pct"],
                "url": deal["url"],
                "image_url": deal.get("image_url"),
                "message": message,
                "category": deal.get("category"),
                "is_super_promo": deal.get("is_super_promo", False),
                "savings_brl": deal.get("savings_brl"),
                "offer_key": deal.get("offer_key"),
                "product_key": deal.get("product_key"),
            }
        )
    return messages


def save_messages_file(
    messages: list[dict[str, Any]],
    now: datetime,
    output_path: str | None = None,
) -> str | None:
    """Persist message payloads to disk for inspection/debugging."""
    if not messages:
        return None

    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%d_%H%M%S")
    destination = output_path or str(MESSAGES_DIR / f"deals_{ts}.json")
    Path(destination).write_text(
        json.dumps(
            {
                "messages": messages,
                "count": len(messages),
                "generated_at": now.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def print_messages(messages: list[dict[str, Any]]) -> None:
    """Print formatted deal messages to stdout."""
    for msg in messages:
        print(f"\n{'=' * 50}")
        print(msg["message"])
        print(f"{'=' * 50}")


def _send_whatsapp_deals(
    parser: argparse.ArgumentParser,
    deals: list[dict[str, Any]],
    group_name: str,
    *,
    headed: bool,
    reset_session: bool,
) -> dict[str, Any]:
    """Send deals through the WhatsApp sender using the normalized shape."""
    if not group_name:
        parser.error(
            "Set WHATSAPP_GROUP in .env or pass --whatsapp-group when using --send-whatsapp"
        )

    from send_to_whatsapp import send_deals_to_whatsapp

    print(f"\nSending {len(deals)} deal(s) to WhatsApp group: {group_name}...")
    return send_deals_to_whatsapp(
        deals=[
            {
                "title": deal["title"],
                "url": deal["url"],
                "dedup_key": deal.get("offer_key") or deal.get("dedup_key") or deal["url"],
                "image_url": deal.get("image_url"),
                "message": deal.get("message") or format_deal_message(deal),
            }
            for deal in deals
        ],
        group_name=group_name,
        headed=headed,
        reset_session=reset_session,
    )


def handle_cadence_scan(
    parser: argparse.ArgumentParser,
    deals: list[dict[str, Any]],
    args: argparse.Namespace,
    now: datetime,
) -> None:
    """Run the cadence-v1 scan path: queue normals and send super promos."""
    sent_data = load_sent_deals()
    queue = load_deal_queue()
    eligible_deals = []
    skipped_sent = 0
    skipped_unqualified = 0

    for deal in deals:
        if not qualifies_normal(deal) and not deal.get("is_super_promo"):
            skipped_unqualified += 1
            continue
        if not can_send_again(deal, sent_data, now=now):
            skipped_sent += 1
            continue
        eligible_deals.append(deal)

    if skipped_unqualified:
        print(f"Skipped {skipped_unqualified} deals outside category thresholds")
    if skipped_sent:
        print(f"Skipped {skipped_sent} deals blocked by cooldown/dedup")

    messages = build_messages_payload(eligible_deals)
    output_path = save_messages_file(messages, now, args.output)
    if output_path:
        print(f"Saved to: {output_path}")
        print_messages(messages)

    normal_deals = [deal for deal in eligible_deals if not deal.get("is_super_promo")]
    super_deals = [deal for deal in eligible_deals if deal.get("is_super_promo")]

    for deal in normal_deals:
        enqueue_or_update_normal(queue, deal, now)

    group = resolve_whatsapp_group(args.whatsapp_group)
    if super_deals and args.send_whatsapp:
        results = _send_whatsapp_deals(
            parser,
            super_deals,
            group,
            headed=args.headed,
            reset_session=args.reset_whatsapp_session,
        )
        print(f"\nImmediate super-promo results: {results['sent']} sent, {results['failed']} failed")

        successful_keys = set(results.get("successful_keys", []))
        if successful_keys:
            successful_deals = [
                deal for deal in super_deals
                if deal["offer_key"] in successful_keys
            ]
            mark_deals_as_sent(successful_deals, sent_data=sent_data, auto_save=True)

        for deal in super_deals:
            if deal["offer_key"] not in successful_keys:
                enqueue_urgent_retry(queue, deal, now)
    else:
        for deal in super_deals:
            enqueue_urgent_retry(queue, deal, now)

    mark_scan_run(queue, now)
    save_deal_queue(queue)

    print(f"\nCadence scan summary: {len(normal_deals)} queued normal, {len(super_deals)} super promo")


def handle_legacy_flow(
    parser: argparse.ArgumentParser,
    deals: list[dict[str, Any]],
    args: argparse.Namespace,
    now: datetime,
) -> None:
    """Keep the direct scan-and-send flow working for manual use."""
    unique_deals, sent_data = filter_new_deals(
        deals,
        auto_save=not args.send_whatsapp,
        mark_as_sent=not args.send_whatsapp,
    )
    skipped = len(deals) - len(unique_deals)
    if skipped > 0:
        print(f"Skipped {skipped} already-sent deals")

    print(f"\nTotal new deals: {len(unique_deals)}")
    messages = build_messages_payload(unique_deals)
    output_path = save_messages_file(messages, now, args.output)
    if output_path:
        print(f"Saved to: {output_path}")
        print_messages(messages)
    else:
        print("No deals found matching criteria.")

    if args.send_whatsapp and unique_deals:
        group = resolve_whatsapp_group(args.whatsapp_group)
        results = _send_whatsapp_deals(
            parser,
            unique_deals,
            group,
            headed=args.headed,
            reset_session=args.reset_whatsapp_session,
        )

        print(f"\nWhatsApp results: {results['sent']} sent, {results['failed']} failed")
        if results["errors"]:
            for err in results["errors"]:
                print(f"  - {err['title']}: {err['reason']}")

        successful_keys = set(results.get("successful_keys", []))
        if successful_keys:
            mark_deals_as_sent(
                [
                    deal for deal in unique_deals
                    if deal.get("offer_key", deal["dedup_key"]) in successful_keys
                ],
                sent_data=sent_data,
                auto_save=True,
            )


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Scan marketplaces for products with displayed discounts."
    )
    parser.add_argument("query", nargs="?", help="Search query (omit if using --all)")
    parser.add_argument("--all", action="store_true", help="Scan the configured hardware/peripheral categories")
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Cadence mode: enqueue normal deals and send super promos immediately",
    )
    parser.add_argument("--max-results", type=int, default=15, help="Max results per marketplace/query")
    parser.add_argument("--min-discount", type=float, default=10.0, help="Minimum discount %% to include")
    parser.add_argument("--marketplaces", default="amazon_br,mercadolivre_br", help="Comma-separated marketplaces")
    parser.add_argument("--output", help="Path to save messages JSON")
    parser.add_argument("--send-whatsapp", action="store_true", help="Send deals to WhatsApp after scanning")
    parser.add_argument(
        "--whatsapp-group",
        default="",
        help="WhatsApp group name (defaults to WHATSAPP_GROUP from .env)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Open browser window for WhatsApp (needed for first-time QR scan)",
    )
    parser.add_argument(
        "--reset-whatsapp-session",
        action="store_true",
        help="Delete the persisted WhatsApp Web session before opening the browser",
    )
    args = parser.parse_args()

    if not args.query and not args.all:
        parser.error("Provide a query or use --all")

    marketplaces = [m.strip() for m in args.marketplaces.split(",")]
    queries = get_queries() if args.all else [args.query]

    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Scanning for deals (min {args.min_discount}% off)...\n")

    scanned_deals = scan_all(args.max_results, args.min_discount, marketplaces, queries)
    unique_deals = deduplicate_run_deals(scanned_deals)
    prepared_deals = [prepare_deal_for_selection(deal) for deal in unique_deals]
    apply_affiliate_links(prepared_deals)

    if args.scan_only:
        handle_cadence_scan(parser, prepared_deals, args, now)
        return

    handle_legacy_flow(parser, prepared_deals, args, now)


if __name__ == "__main__":
    main()
