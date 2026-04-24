#!/usr/bin/env python3

"""Dispatch pending cadence deals to WhatsApp in category-balanced batches."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from config import configure_utf8_stdio, resolve_whatsapp_group
from deal_queue import (
    drop_expired_entries,
    increment_retry_count,
    load_deal_queue,
    mark_batch_run,
    remove_entries_by_offer_keys,
    save_deal_queue,
)
from deal_selection import round_robin_select
from send_to_whatsapp import send_deals_to_whatsapp
from utils import load_sent_deals, mark_deals_as_sent


def _group_normal_queue(entries: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry.get("category", ""), []).append(entry)
    return grouped


def dispatch_pending_deals(
    *,
    group_name: str,
    headed: bool = False,
    reset_session: bool = False,
) -> dict:
    """Dispatch pending cadence deals and update queue/sent metadata."""
    queue = drop_expired_entries(load_deal_queue())
    urgent_entries = list(queue.get("urgent_retry", []))
    normal_entries = round_robin_select(_group_normal_queue(queue.get("normal", [])))
    deals_to_send = urgent_entries + normal_entries

    if not deals_to_send:
        mark_batch_run(queue)
        save_deal_queue(queue)
        return {"sent": 0, "failed": 0, "errors": [], "successful_keys": []}

    results = send_deals_to_whatsapp(
        deals=[
            {
                "title": deal["title"],
                "url": deal["url"],
                "dedup_key": deal.get("offer_key") or deal.get("dedup_key") or deal["url"],
                "image_url": deal.get("image_url"),
                "message": deal.get("message", ""),
            }
            for deal in deals_to_send
        ],
        group_name=group_name,
        headed=headed,
        reset_session=reset_session,
    )

    successful_keys = set(results.get("successful_keys", []))
    failed_keys = {
        deal["offer_key"]
        for deal in deals_to_send
        if deal["offer_key"] not in successful_keys
    }

    if successful_keys:
        sent_data = load_sent_deals()
        successful_deals = [
            deal for deal in deals_to_send
            if deal["offer_key"] in successful_keys
        ]
        mark_deals_as_sent(successful_deals, sent_data=sent_data, auto_save=True)

    remove_entries_by_offer_keys(queue, successful_keys)
    increment_retry_count(queue, failed_keys)
    mark_batch_run(queue, datetime.now(timezone.utc))
    save_deal_queue(queue)

    return results


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Dispatch pending cadence deals to WhatsApp."
    )
    parser.add_argument(
        "--group",
        default="",
        help="Name of the WhatsApp group to send to (defaults to WHATSAPP_GROUP from .env)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Open browser window (only needed to refresh the WhatsApp session)",
    )
    parser.add_argument(
        "--reset-session",
        action="store_true",
        help="Delete the persisted WhatsApp Web session before opening the browser",
    )
    args = parser.parse_args()

    group_name = resolve_whatsapp_group(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Dispatching pending cadence deals...\n")

    results = dispatch_pending_deals(
        group_name=group_name,
        headed=args.headed,
        reset_session=args.reset_session,
    )

    print(f"Results: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  - {err['title']}: {err['reason']}")


if __name__ == "__main__":
    main()
