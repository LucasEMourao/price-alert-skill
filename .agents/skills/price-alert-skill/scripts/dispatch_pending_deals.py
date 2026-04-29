#!/usr/bin/env python3

"""One-shot drain helper for the single-sender cadence model."""

from __future__ import annotations

from config import configure_utf8_stdio, resolve_whatsapp_group
from core.entrypoints.dispatch_cli import main as run_dispatch_cli
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
    run_dispatch_cli(
        configure_utf8_stdio_fn=configure_utf8_stdio,
        resolve_whatsapp_group_fn=resolve_whatsapp_group,
        dispatch_pending_deals_fn=dispatch_pending_deals,
        logger=print,
    )


if __name__ == "__main__":
    main()
