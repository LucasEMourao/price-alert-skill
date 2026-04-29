"""CLI entrypoint for marketplace scanning flows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Callable


def main(
    *,
    configure_utf8_stdio_fn: Callable[[], None],
    get_queries_fn: Callable[[], list[str]],
    scan_all_fn: Callable[[int, float, list[str], list[str]], list[dict[str, Any]]],
    deduplicate_run_deals_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    prepare_deal_for_selection_fn: Callable[[dict[str, Any]], dict[str, Any]],
    apply_affiliate_links_fn: Callable[[list[dict[str, Any]]], None],
    handle_cadence_scan_fn: Callable[[argparse.ArgumentParser, list[dict[str, Any]], argparse.Namespace, datetime], None],
    handle_legacy_flow_fn: Callable[[argparse.ArgumentParser, list[dict[str, Any]], argparse.Namespace, datetime], None],
    logger: Callable[[str], None] = print,
    now_fn: Callable[[], datetime] | None = None,
) -> None:
    """Parse CLI args and orchestrate the scan flow through injected dependencies."""
    configure_utf8_stdio_fn()
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
    queries = get_queries_fn() if args.all else [args.query]

    now = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    logger(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Scanning for deals (min {args.min_discount}% off)...\n")

    scanned_deals = scan_all_fn(args.max_results, args.min_discount, marketplaces, queries)
    unique_deals = deduplicate_run_deals_fn(scanned_deals)
    prepared_deals = [prepare_deal_for_selection_fn(deal) for deal in unique_deals]
    apply_affiliate_links_fn(prepared_deals)

    if args.scan_only:
        handle_cadence_scan_fn(parser, prepared_deals, args, now)
        return

    handle_legacy_flow_fn(parser, prepared_deals, args, now)
