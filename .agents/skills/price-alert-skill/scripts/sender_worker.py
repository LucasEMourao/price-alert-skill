#!/usr/bin/env python3

"""Single serial sender for WhatsApp delivery using expiring deal pools."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import configure_utf8_stdio, resolve_whatsapp_group
from core.adapters.whatsapp_sender import (
    WhatsAppDealChatSenderAdapter,
    WhatsAppSessionCloserAdapter,
    WhatsAppSessionOpenerAdapter,
)
from core.application.sender_use_case import (
    run_sender_loop as application_run_sender_loop,
    select_next_deal as application_select_next_deal,
)
from deal_queue import (
    get_sendable_entries,
    load_deal_queue,
    mark_deal_failed,
    mark_sender_tick,
    prune_expired_entries,
    remove_entry_by_offer_key,
    save_deal_queue,
)
from deal_selection import CADENCE_CONFIG, sort_deals_for_sending
from utils import load_sent_deals, mark_deals_as_sent


ROOT = Path(__file__).resolve().parents[1]
SENDER_LOCK_FILE = ROOT / "data" / "sender_worker.lock"
STOP_REQUEST_FILE = ROOT / "data" / "sender_stop.request"
_WHATSAPP_SESSION_OPENER = WhatsAppSessionOpenerAdapter()
_WHATSAPP_SESSION_CLOSER = WhatsAppSessionCloserAdapter()
_WHATSAPP_DEAL_CHAT_SENDER = WhatsAppDealChatSenderAdapter()
open_whatsapp_session = _WHATSAPP_SESSION_OPENER
close_whatsapp_session = _WHATSAPP_SESSION_CLOSER
send_deal_in_open_chat = _WHATSAPP_DEAL_CHAT_SENDER


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_lock_pid() -> int | None:
    try:
        content = SENDER_LOCK_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    for part in content.split():
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _pid_is_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_sender_lock(stale_after_seconds: int = 43200) -> int | None:
    SENDER_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SENDER_LOCK_FILE.exists():
        lock_pid = _read_lock_pid()
        if not _pid_is_running(lock_pid):
            try:
                SENDER_LOCK_FILE.unlink()
            except OSError:
                pass

    if SENDER_LOCK_FILE.exists():
        age_seconds = time.time() - SENDER_LOCK_FILE.stat().st_mtime
        if age_seconds > stale_after_seconds:
            try:
                SENDER_LOCK_FILE.unlink()
            except OSError:
                pass

    try:
        fd = os.open(str(SENDER_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None

    payload = f"pid={os.getpid()} started_at={_utc_now().isoformat()}".encode("utf-8")
    os.write(fd, payload)
    return fd


def _release_sender_lock(fd: int | None) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        SENDER_LOCK_FILE.unlink()
    except OSError:
        pass


def _stop_requested() -> bool:
    return STOP_REQUEST_FILE.exists()


def _select_next_deal(
    queue: dict[str, Any],
    *,
    non_urgent_index: int,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, int]:
    return application_select_next_deal(
        queue,
        non_urgent_index=non_urgent_index,
        now=now,
        get_sendable_entries_fn=get_sendable_entries,
        sort_deals_for_sending_fn=sort_deals_for_sending,
        non_urgent_lane_sequence=tuple(CADENCE_CONFIG["non_urgent_lane_sequence"]),
    )


def run_sender(
    *,
    group_name: str,
    headed: bool = False,
    reset_session: bool = False,
    continuous: bool = False,
    poll_seconds: int | None = None,
    max_messages: int | None = None,
    idle_exit_seconds: int | None = None,
) -> dict[str, Any]:
    """Run the single sender loop once or continuously."""
    lock_fd = _acquire_sender_lock()
    if lock_fd is None:
        print("Another sender worker is already running. Exiting.")
        return {"sent": 0, "failed": 0, "errors": [], "skipped_due_to_lock": True}

    poll_seconds = int(poll_seconds or CADENCE_CONFIG["sender_poll_seconds"])
    idle_exit_seconds = (
        int(idle_exit_seconds)
        if idle_exit_seconds is not None
        else None
    )

    try:
        return application_run_sender_loop(
            group_name=group_name,
            headed=headed,
            reset_session=reset_session,
            continuous=continuous,
            poll_seconds=poll_seconds,
            max_messages=max_messages,
            idle_exit_seconds=idle_exit_seconds,
            stop_requested_fn=_stop_requested,
            now_fn=_utc_now,
            load_deal_queue_fn=load_deal_queue,
            prune_expired_entries_fn=prune_expired_entries,
            mark_sender_tick_fn=mark_sender_tick,
            save_deal_queue_fn=save_deal_queue,
            get_sendable_entries_fn=get_sendable_entries,
            sort_deals_for_sending_fn=sort_deals_for_sending,
            non_urgent_lane_sequence=tuple(CADENCE_CONFIG["non_urgent_lane_sequence"]),
            open_whatsapp_session_fn=open_whatsapp_session,
            send_deal_in_open_chat_fn=send_deal_in_open_chat,
            close_whatsapp_session_fn=close_whatsapp_session,
            load_sent_deals_fn=load_sent_deals,
            mark_deals_as_sent_fn=mark_deals_as_sent,
            remove_entry_by_offer_key_fn=remove_entry_by_offer_key,
            mark_deal_failed_fn=mark_deal_failed,
            sleep_fn=time.sleep,
            logger=print,
        )
    finally:
        _release_sender_lock(lock_fd)


def main() -> None:
    configure_utf8_stdio()
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
        default=CADENCE_CONFIG["sender_poll_seconds"],
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

    group_name = resolve_whatsapp_group(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    now = _utc_now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Starting sender worker...\n")

    results = run_sender(
        group_name=group_name,
        headed=args.headed,
        reset_session=args.reset_session,
        continuous=args.continuous,
        poll_seconds=args.poll_seconds,
        max_messages=args.max_messages,
        idle_exit_seconds=args.idle_exit_seconds,
    )

    print(f"\nResults: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  - {err['title']}: {err['reason']}")


if __name__ == "__main__":
    main()
