#!/usr/bin/env python3

"""Single serial sender for WhatsApp delivery using expiring deal pools."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from price_alert_skill.config import (
    configure_utf8_stdio,
    resolve_allowed_beauty_brand_names,
    resolve_price_alert_send_marketplaces,
    resolve_whatsapp_send_interval_seconds,
    resolve_whatsapp_group,
    resolve_whatsapp_sender_backend,
)
from price_alert_skill.core.adapters.baileys_sender import (
    BaileysDealChatSenderAdapter,
    BaileysSessionCloserAdapter,
    BaileysSessionOpenerAdapter,
)
from price_alert_skill.core.adapters.whatsapp_sender import (
    WhatsAppDealChatSenderAdapter,
    WhatsAppSessionCloserAdapter,
    WhatsAppSessionOpenerAdapter,
)
from price_alert_skill.core.entrypoints.sender_cli import main as run_sender_cli
from price_alert_skill.core.application.sender_use_case import (
    run_sender_loop as application_run_sender_loop,
    select_next_deal as application_select_next_deal,
)
from price_alert_skill.deal_queue import (
    get_sendable_entries,
    load_deal_queue,
    mark_deal_failed,
    mark_sender_tick,
    prune_expired_entries,
    remove_entry_by_offer_key,
    save_deal_queue,
)
from price_alert_skill.deal_selection import CADENCE_CONFIG, sort_deals_for_sending
from price_alert_skill.paths import resolve_data_dir
from price_alert_skill.utils import load_sent_deals, mark_deals_as_sent


DATA_DIR = resolve_data_dir()
SENDER_LOCK_FILE = DATA_DIR / "sender_worker.lock"
STOP_REQUEST_FILE = DATA_DIR / "sender_stop.request"


def _build_whatsapp_sender_adapters(backend: str | None = None):
    """Build sender adapters for the configured WhatsApp backend."""
    resolved_backend = (backend or resolve_whatsapp_sender_backend()).strip().lower()
    if resolved_backend == "baileys":
        return (
            BaileysSessionOpenerAdapter(),
            BaileysSessionCloserAdapter(),
            BaileysDealChatSenderAdapter(),
        )
    return (
        WhatsAppSessionOpenerAdapter(),
        WhatsAppSessionCloserAdapter(),
        WhatsAppDealChatSenderAdapter(),
    )

_ACTIVE_WHATSAPP_SENDER_BACKEND = resolve_whatsapp_sender_backend()
_WHATSAPP_SEND_INTERVAL_SECONDS = resolve_whatsapp_send_interval_seconds(
    _ACTIVE_WHATSAPP_SENDER_BACKEND
)

(
    _WHATSAPP_SESSION_OPENER,
    _WHATSAPP_SESSION_CLOSER,
    _WHATSAPP_DEAL_CHAT_SENDER,
) = _build_whatsapp_sender_adapters(_ACTIVE_WHATSAPP_SENDER_BACKEND)
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
    product_profile: str | None = None,
) -> tuple[dict[str, Any] | None, int]:
    return application_select_next_deal(
        queue,
        non_urgent_index=non_urgent_index,
        now=now,
        product_profile=product_profile,
        get_sendable_entries_fn=_get_sendable_entries_for_sender,
        sort_deals_for_sending_fn=sort_deals_for_sending,
        non_urgent_lane_sequence=tuple(CADENCE_CONFIG["non_urgent_lane_sequence"]),
    )


def _get_sendable_entries_for_sender(
    queue: dict[str, Any],
    lane: str,
    *,
    now: datetime | str | None = None,
    product_profile: str | None = None,
) -> list[dict[str, Any]]:
    return get_sendable_entries(
        queue,
        lane,
        now=now,
        product_profile=product_profile,
        allowed_beauty_brand_names=resolve_allowed_beauty_brand_names(),
        allowed_marketplaces=resolve_price_alert_send_marketplaces(),
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
    product_profile: str | None = None,
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

    print(f"Using WhatsApp sender backend: {_ACTIVE_WHATSAPP_SENDER_BACKEND}")
    if _WHATSAPP_SEND_INTERVAL_SECONDS > 0:
        print(f"Using WhatsApp send interval: {_WHATSAPP_SEND_INTERVAL_SECONDS:g}s")

    try:
        return application_run_sender_loop(
            group_name=group_name,
            headed=headed,
            reset_session=reset_session,
            continuous=continuous,
            poll_seconds=poll_seconds,
            max_messages=max_messages,
            idle_exit_seconds=idle_exit_seconds,
            product_profile=product_profile,
            send_interval_seconds=_WHATSAPP_SEND_INTERVAL_SECONDS,
            stop_requested_fn=_stop_requested,
            now_fn=_utc_now,
            load_deal_queue_fn=load_deal_queue,
            prune_expired_entries_fn=prune_expired_entries,
            mark_sender_tick_fn=mark_sender_tick,
            save_deal_queue_fn=save_deal_queue,
            get_sendable_entries_fn=_get_sendable_entries_for_sender,
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
    run_sender_cli(
        configure_utf8_stdio_fn=configure_utf8_stdio,
        resolve_whatsapp_group_fn=resolve_whatsapp_group,
        run_sender_fn=run_sender,
        default_poll_seconds=int(CADENCE_CONFIG["sender_poll_seconds"]),
        logger=print,
        now_fn=_utc_now,
    )


if __name__ == "__main__":
    main()
