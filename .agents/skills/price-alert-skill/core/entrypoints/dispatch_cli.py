"""CLI entrypoint for one-shot queue dispatches."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Callable


def main(
    *,
    configure_utf8_stdio_fn: Callable[[], None],
    resolve_whatsapp_group_fn: Callable[[str], str],
    dispatch_pending_deals_fn: Callable[..., dict[str, Any]],
    logger: Callable[[str], None] = print,
    now_fn: Callable[[], datetime] | None = None,
) -> None:
    """Parse CLI args and run a one-shot dispatch through injected dependencies."""
    configure_utf8_stdio_fn()
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

    group_name = resolve_whatsapp_group_fn(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    now = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    logger(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Dispatching queued deals...\n")

    results = dispatch_pending_deals_fn(
        group_name=group_name,
        headed=args.headed,
        reset_session=args.reset_session,
        max_messages=args.max_messages,
    )

    logger(f"Results: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        for err in results["errors"]:
            logger(f"  - {err['title']}: {err['reason']}")
