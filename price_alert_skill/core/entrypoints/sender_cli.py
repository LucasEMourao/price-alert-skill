"""CLI entrypoint for the single sender worker."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Callable


def main(
    *,
    configure_utf8_stdio_fn: Callable[[], None],
    resolve_whatsapp_group_fn: Callable[[str], str],
    run_sender_fn: Callable[..., dict[str, Any]],
    default_poll_seconds: int,
    logger: Callable[[str], None] = print,
    now_fn: Callable[[], datetime] | None = None,
) -> None:
    """Parse CLI args and invoke the sender worker through injected dependencies."""
    configure_utf8_stdio_fn()
    parser = argparse.ArgumentParser(
        description="Run the single serial WhatsApp sender for queued deals."
    )
    parser.add_argument(
        "--group",
        default="",
        help="Name of the WhatsApp group to send to (defaults to WHATSAPP_GROUP from .env)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Open the browser window instead of using headless mode.",
    )
    parser.add_argument(
        "--reset-session",
        action="store_true",
        help="Delete the persisted WhatsApp Web session before opening the browser.",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Keep polling for new deals instead of processing a single run.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=default_poll_seconds,
        help="Seconds to wait between idle polls in continuous mode.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        help="Optional cap on how many deals this invocation should process.",
    )
    parser.add_argument(
        "--idle-exit-seconds",
        type=int,
        help="Optional idle timeout for continuous mode. If omitted, the worker keeps polling.",
    )
    args = parser.parse_args()

    group_name = resolve_whatsapp_group_fn(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    now = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    logger(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Starting sender worker...\n")

    results = run_sender_fn(
        group_name=group_name,
        headed=args.headed,
        reset_session=args.reset_session,
        continuous=args.continuous,
        poll_seconds=args.poll_seconds,
        max_messages=args.max_messages,
        idle_exit_seconds=args.idle_exit_seconds,
    )

    logger(f"\nResults: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        for err in results["errors"]:
            logger(f"  - {err['title']}: {err['reason']}")
