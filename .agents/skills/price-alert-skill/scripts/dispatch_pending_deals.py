#!/usr/bin/env python3

"""One-shot drain helper for the single-sender cadence model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from config import configure_utf8_stdio, resolve_whatsapp_group
from sender_worker import run_sender


def dispatch_pending_deals(
    *,
    group_name: str,
    headed: bool = False,
    reset_session: bool = False,
    max_messages: int = 4,
) -> dict:
    """Process a small sender run and then exit."""
    return run_sender(
        group_name=group_name,
        headed=headed,
        reset_session=reset_session,
        continuous=False,
        max_messages=max_messages,
    )


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Dispatch a one-shot batch of queued deals to WhatsApp."
    )
    parser.add_argument(
        "--group",
        default="",
        help="Name of the WhatsApp group to send to (defaults to WHATSAPP_GROUP from .env)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Open browser window (only needed to refresh the WhatsApp session).",
    )
    parser.add_argument(
        "--reset-session",
        action="store_true",
        help="Delete the persisted WhatsApp Web session before opening the browser.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=4,
        help="Maximum number of deals to process in this invocation.",
    )
    args = parser.parse_args()

    group_name = resolve_whatsapp_group(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Dispatching queued deals...\n")

    results = dispatch_pending_deals(
        group_name=group_name,
        headed=args.headed,
        reset_session=args.reset_session,
        max_messages=args.max_messages,
    )

    print(f"Results: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  - {err['title']}: {err['reason']}")


if __name__ == "__main__":
    main()
