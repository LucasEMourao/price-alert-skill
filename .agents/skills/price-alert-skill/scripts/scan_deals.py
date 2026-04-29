#!/usr/bin/env python3

"""Scan marketplaces for discounted products and prepare/send deal messages."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import configure_utf8_stdio, resolve_whatsapp_group
from core.adapters.meli_affiliate_links import MeliAffiliateLinkGenerator
from core.adapters.whatsapp_sender import WhatsAppBatchSender
from core.application.scan_use_case import (
    apply_affiliate_links as application_apply_affiliate_links,
    build_messages_payload as application_build_messages_payload,
    deduplicate_run_deals as application_deduplicate_run_deals,
    extract_deals_from_products as application_extract_deals_from_products,
    print_messages as application_print_messages,
    run_cadence_scan as application_run_cadence_scan,
    run_legacy_flow as application_run_legacy_flow,
    save_messages_file as application_save_messages_file,
    scan_all as application_scan_all,
    scan_marketplace as application_scan_marketplace,
)
from deal_queue import (
    begin_scan_run,
    load_deal_queue,
    prune_expired_entries,
    remove_entry_by_product_key,
    save_deal_queue,
    upsert_pool_deal,
)
from deal_selection import get_queries, prepare_deal_for_selection
from fetch_amazon_br import run as run_amazon
from fetch_ml_browser import run as run_mercadolivre_browser
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
_AFFILIATE_LINK_GENERATOR = MeliAffiliateLinkGenerator()
_WHATSAPP_BATCH_SENDER = WhatsAppBatchSender()


def extract_deals_from_products(
    products: list[dict[str, Any]],
    marketplace: str,
    query: str,
    min_discount: float,
) -> list[dict[str, Any]]:
    """Extract products that have a displayed discount >= min_discount."""
    return application_extract_deals_from_products(
        products,
        marketplace,
        query,
        min_discount,
        calculate_discount_fn=calculate_discount,
    )


def scan_marketplace(
    marketplace: str,
    query: str,
    max_results: int,
    min_discount: float,
) -> list[dict[str, Any]]:
    """Scan a single marketplace for deals."""
    return application_scan_marketplace(
        marketplace,
        query,
        max_results,
        min_discount,
        amazon_runner=run_amazon,
        mercadolivre_runner=run_mercadolivre_browser,
        calculate_discount_fn=calculate_discount,
    )


def scan_all(
    max_results: int,
    min_discount: float,
    marketplaces: list[str],
    queries: list[str],
) -> list[dict[str, Any]]:
    """Scan multiple queries across marketplaces."""
    return application_scan_all(
        max_results,
        min_discount,
        marketplaces,
        queries,
        scan_marketplace_fn=scan_marketplace,
        logger=print,
    )


def deduplicate_run_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate deals within the same scan run by product URL."""
    return application_deduplicate_run_deals(deals)


def apply_affiliate_links(deals: list[dict[str, Any]]) -> None:
    """Replace Mercado Livre URLs with generated affiliate links when possible."""
    application_apply_affiliate_links(
        deals,
        generate_links_fn=_AFFILIATE_LINK_GENERATOR,
        logger=print,
    )


def build_messages_payload(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build printable/savable message payloads from normalized deals."""
    return application_build_messages_payload(
        deals,
        format_message_fn=format_deal_message,
    )


def save_messages_file(
    messages: list[dict[str, Any]],
    now: datetime,
    output_path: str | None = None,
) -> str | None:
    """Persist message payloads to disk for inspection/debugging."""
    return application_save_messages_file(messages, now, MESSAGES_DIR, output_path)


def print_messages(messages: list[dict[str, Any]]) -> None:
    """Print formatted deal messages to stdout."""
    application_print_messages(messages, logger=print)


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

    print(f"\nSending {len(deals)} deal(s) to WhatsApp group: {group_name}...")
    return _WHATSAPP_BATCH_SENDER(
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
    """Collect deals into expiring pools for the single-sender flow."""
    if args.send_whatsapp:
        print(
            "  NOTE: scan-only no longer sends to WhatsApp directly. "
            "Use sender_worker.py to process the pools."
        )
    application_run_cadence_scan(
        deals,
        now=now,
        output_path=args.output,
        load_sent_deals_fn=load_sent_deals,
        load_deal_queue_fn=load_deal_queue,
        begin_scan_run_fn=begin_scan_run,
        can_send_again_fn=can_send_again,
        remove_entry_by_product_key_fn=remove_entry_by_product_key,
        upsert_pool_deal_fn=upsert_pool_deal,
        build_messages_payload_fn=build_messages_payload,
        save_messages_file_fn=lambda messages, scan_now, output: save_messages_file(messages, scan_now, output),
        prune_expired_entries_fn=prune_expired_entries,
        save_deal_queue_fn=save_deal_queue,
        format_message_fn=format_deal_message,
        logger=print,
    )


def handle_legacy_flow(
    parser: argparse.ArgumentParser,
    deals: list[dict[str, Any]],
    args: argparse.Namespace,
    now: datetime,
) -> None:
    """Keep the direct scan-and-send flow working for manual use."""
    group = resolve_whatsapp_group(args.whatsapp_group) if args.send_whatsapp else ""
    if args.send_whatsapp and not group:
        parser.error(
            "Set WHATSAPP_GROUP in .env or pass --whatsapp-group when using --send-whatsapp"
        )

    application_run_legacy_flow(
        deals,
        now=now,
        output_path=args.output,
        send_whatsapp=args.send_whatsapp,
        group_name=group,
        headed=args.headed,
        reset_session=args.reset_whatsapp_session,
        filter_new_deals_fn=filter_new_deals,
        build_messages_payload_fn=build_messages_payload,
        save_messages_file_fn=lambda messages, scan_now, output: save_messages_file(messages, scan_now, output),
        print_messages_fn=print_messages,
        whatsapp_sender_fn=(
            lambda **kwargs: _send_whatsapp_deals(
                parser,
                kwargs["deals"],
                kwargs["group_name"],
                headed=kwargs["headed"],
                reset_session=kwargs["reset_session"],
            )
        ) if args.send_whatsapp else None,
        mark_deals_as_sent_fn=mark_deals_as_sent,
        logger=print,
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
        help="Cadence mode: collect deals into expiring pools for the single sender",
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
