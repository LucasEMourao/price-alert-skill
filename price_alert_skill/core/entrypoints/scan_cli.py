"""CLI entrypoint for marketplace scanning flows."""

from __future__ import annotations

import argparse
from collections import Counter
import os
from datetime import datetime, timezone
from typing import Any, Callable

from price_alert_skill.log_time import format_brazil_log_timestamp


def _log_brand_filter_summary(
    deals: list[dict[str, Any]],
    *,
    logger: Callable[[str], None],
) -> None:
    beauty_deals = [
        deal
        for deal in deals
        if str(deal.get("product_profile") or "").strip().lower() == "beauty"
    ]
    if not beauty_deals:
        return

    allowed = [
        deal
        for deal in beauty_deals
        if bool(deal.get("brand_filter_passed", True))
    ]
    filtered = len(beauty_deals) - len(allowed)
    logger(
        "\nBeauty brand filter: "
        f"{len(allowed)}/{len(beauty_deals)} allowed, {filtered} filtered"
    )

    brand_counts = Counter(
        str(deal.get("allowed_brand") or "").strip()
        for deal in allowed
        if deal.get("allowed_brand")
    )
    if brand_counts:
        summary = ", ".join(
            f"{brand}: {count}"
            for brand, count in brand_counts.most_common(8)
        )
        logger(f"Allowed beauty brands found: {summary}")


def main(
    *,
    configure_utf8_stdio_fn: Callable[[], None],
    get_queries_fn: Callable[[str | None, str | None], list[str]],
    scan_all_fn: Callable[[int, float, list[str], list[str]], list[dict[str, Any]]],
    deduplicate_run_deals_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    prepare_deal_for_selection_fn: Callable[[dict[str, Any]], dict[str, Any]],
    collapse_prepared_deals_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
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
    parser.add_argument("--all", action="store_true", help="Scan all queries from the configured product profile")
    parser.add_argument(
        "--profile",
        default=os.environ.get("PRICE_ALERT_SCAN_PROFILE", "tech"),
        help="Product query profile to use with --all (default: PRICE_ALERT_SCAN_PROFILE or tech)",
    )
    parser.add_argument(
        "--query-categories",
        default=os.environ.get("PRICE_ALERT_SCAN_CATEGORIES", ""),
        help="Comma-separated profile categories to scan with --all (default: all profile categories)",
    )
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
    try:
        queries = get_queries_fn(args.profile, args.query_categories) if args.all else [args.query]
    except ValueError as exc:
        parser.error(str(exc))

    now = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    logger(
        f"[{format_brazil_log_timestamp(now)}] Scanning for deals (min {args.min_discount}% off)...\n"
    )
    if args.all:
        logger(f"Using scan profile: {args.profile}\n")
        if args.query_categories:
            logger(f"Using scan categories: {args.query_categories}\n")

    scanned_deals = scan_all_fn(args.max_results, args.min_discount, marketplaces, queries)
    unique_deals = deduplicate_run_deals_fn(scanned_deals)
    prepared_deals = [prepare_deal_for_selection_fn(deal) for deal in unique_deals]
    if collapse_prepared_deals_fn is not None:
        prepared_deals = collapse_prepared_deals_fn(prepared_deals)
    _log_brand_filter_summary(prepared_deals, logger=logger)
    prepared_deals = [
        deal
        for deal in prepared_deals
        if bool(deal.get("brand_filter_passed", True))
    ]
    apply_affiliate_links_fn(prepared_deals)

    if args.scan_only:
        handle_cadence_scan_fn(parser, prepared_deals, args, now)
        return

    handle_legacy_flow_fn(parser, prepared_deals, args, now)
