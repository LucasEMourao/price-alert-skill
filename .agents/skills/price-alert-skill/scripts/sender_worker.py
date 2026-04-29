#!/usr/bin/env python3

"""Single serial sender for WhatsApp delivery using expiring deal pools."""

from __future__ import annotations

import argparse
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import configure_utf8_stdio, resolve_whatsapp_group
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
from send_to_whatsapp import (
    close_whatsapp_session,
    open_whatsapp_session,
    send_deal_in_open_chat,
)
from utils import load_sent_deals, mark_deals_as_sent


ROOT = Path(__file__).resolve().parents[1]
SENDER_LOCK_FILE = ROOT / "data" / "sender_worker.lock"
STOP_REQUEST_FILE = ROOT / "data" / "sender_stop.request"


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
    urgent_entries = sort_deals_for_sending(
        get_sendable_entries(queue, "urgent", now=now)
    )
    if urgent_entries:
        return urgent_entries[0], non_urgent_index

    sequence = tuple(CADENCE_CONFIG["non_urgent_lane_sequence"])
    sequence_length = len(sequence)
    for offset in range(sequence_length):
        lane = sequence[(non_urgent_index + offset) % sequence_length]
        lane_entries = sort_deals_for_sending(
            get_sendable_entries(queue, lane, now=now)
        )
        if lane_entries:
            next_index = (non_urgent_index + offset + 1) % sequence_length
            return lane_entries[0], next_index

    return None, non_urgent_index


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

    results = {"sent": 0, "failed": 0, "errors": [], "skipped_due_to_lock": False}
    session = None
    idle_started_at = time.time()
    non_urgent_index = 0

    try:
        while True:
            if _stop_requested():
                print("Sender stop requested. Shutting down gracefully.")
                break

            now = _utc_now()
            queue = prune_expired_entries(load_deal_queue(), now=now)
            deal, non_urgent_index = _select_next_deal(
                queue,
                non_urgent_index=non_urgent_index,
                now=now,
            )

            if not deal:
                mark_sender_tick(queue, now)
                save_deal_queue(queue)

                if not continuous:
                    break

                if _stop_requested():
                    print("Sender stop requested while idle. Stopping.")
                    break

                if idle_exit_seconds and (time.time() - idle_started_at) >= idle_exit_seconds:
                    print("Sender worker idle timeout reached. Stopping.")
                    break

                time.sleep(poll_seconds)
                continue

            idle_started_at = time.time()
            if session is None:
                try:
                    session = open_whatsapp_session(
                        group_name=group_name,
                        headed=headed,
                        reset_session=reset_session,
                    )
                except Exception as exc:
                    print(f"  WARNING: Failed to open WhatsApp session: {exc}")
                    traceback.print_exc()
                    if not continuous:
                        raise
                    time.sleep(poll_seconds)
                    continue

            print(
                f"\nSending next {deal.get('lane', 'normal')} deal: "
                f"{deal.get('title', '')[:60]}..."
            )
            attempt_result = send_deal_in_open_chat(
                session["page"],
                deal,
                delay_between=5.0,
                max_retries=2,
            )

            refreshed_queue = prune_expired_entries(load_deal_queue(), now=_utc_now())
            if attempt_result["success"]:
                remove_entry_by_offer_key(refreshed_queue, deal["offer_key"])
                sent_data = load_sent_deals()
                mark_deals_as_sent([deal], sent_data=sent_data, auto_save=True)
                results["sent"] += 1
            else:
                mark_deal_failed(refreshed_queue, deal["offer_key"], now=_utc_now())
                results["failed"] += 1
                results["errors"].append(
                    {
                        "title": attempt_result["title"],
                        "url": attempt_result["url"],
                        "reason": attempt_result["reason"],
                    }
                )

            mark_sender_tick(refreshed_queue, _utc_now())
            save_deal_queue(refreshed_queue)

            if max_messages is not None and results["sent"] + results["failed"] >= max_messages:
                break

            if not continuous:
                continue

        return results
    finally:
        close_whatsapp_session(session)
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
