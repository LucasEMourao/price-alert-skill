"""Application orchestration for sender flows."""

from __future__ import annotations

from time import time as monotonic_now
from traceback import print_exc
from typing import Any, Callable


def select_next_deal(
    queue: dict[str, Any],
    *,
    non_urgent_index: int,
    now,
    get_sendable_entries_fn: Callable[..., list[dict[str, Any]]],
    sort_deals_for_sending_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    non_urgent_lane_sequence: tuple[str, ...],
) -> tuple[dict[str, Any] | None, int]:
    """Select the next deal respecting urgent priority and the configured lane ratio."""
    urgent_entries = sort_deals_for_sending_fn(
        get_sendable_entries_fn(queue, "urgent", now=now)
    )
    if urgent_entries:
        return urgent_entries[0], non_urgent_index

    sequence_length = len(non_urgent_lane_sequence)
    for offset in range(sequence_length):
        lane = non_urgent_lane_sequence[(non_urgent_index + offset) % sequence_length]
        lane_entries = sort_deals_for_sending_fn(
            get_sendable_entries_fn(queue, lane, now=now)
        )
        if lane_entries:
            next_index = (non_urgent_index + offset + 1) % sequence_length
            return lane_entries[0], next_index

    return None, non_urgent_index


def run_sender_loop(
    *,
    group_name: str,
    headed: bool,
    reset_session: bool,
    continuous: bool,
    poll_seconds: int,
    max_messages: int | None,
    idle_exit_seconds: int | None,
    stop_requested_fn: Callable[[], bool],
    now_fn: Callable[[], Any],
    load_deal_queue_fn: Callable[[], dict[str, Any]],
    prune_expired_entries_fn: Callable[..., dict[str, Any]],
    mark_sender_tick_fn: Callable[..., dict[str, Any]],
    save_deal_queue_fn: Callable[[dict[str, Any]], None],
    get_sendable_entries_fn: Callable[..., list[dict[str, Any]]],
    sort_deals_for_sending_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    non_urgent_lane_sequence: tuple[str, ...],
    open_whatsapp_session_fn: Callable[..., dict[str, Any]],
    send_deal_in_open_chat_fn: Callable[..., dict[str, Any]],
    close_whatsapp_session_fn: Callable[[dict[str, Any] | None], None],
    load_sent_deals_fn: Callable[[], dict[str, Any]],
    mark_deals_as_sent_fn: Callable[..., dict[str, Any]],
    remove_entry_by_offer_key_fn: Callable[[dict[str, Any], str], bool],
    mark_deal_failed_fn: Callable[..., bool],
    sleep_fn: Callable[[float], None],
    logger: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the single sender loop once or continuously."""
    results = {"sent": 0, "failed": 0, "errors": [], "skipped_due_to_lock": False}
    session = None
    idle_started_at = monotonic_now()
    non_urgent_index = 0

    try:
        while True:
            if stop_requested_fn():
                logger("Sender stop requested. Shutting down gracefully.")
                break

            now = now_fn()
            queue = prune_expired_entries_fn(load_deal_queue_fn(), now=now)
            deal, non_urgent_index = select_next_deal(
                queue,
                non_urgent_index=non_urgent_index,
                now=now,
                get_sendable_entries_fn=get_sendable_entries_fn,
                sort_deals_for_sending_fn=sort_deals_for_sending_fn,
                non_urgent_lane_sequence=non_urgent_lane_sequence,
            )

            if not deal:
                mark_sender_tick_fn(queue, now)
                save_deal_queue_fn(queue)

                if not continuous:
                    break

                if stop_requested_fn():
                    logger("Sender stop requested while idle. Stopping.")
                    break

                if idle_exit_seconds and (monotonic_now() - idle_started_at) >= idle_exit_seconds:
                    logger("Sender worker idle timeout reached. Stopping.")
                    break

                sleep_fn(poll_seconds)
                continue

            idle_started_at = monotonic_now()
            if session is None:
                try:
                    session = open_whatsapp_session_fn(
                        group_name=group_name,
                        headed=headed,
                        reset_session=reset_session,
                    )
                except Exception as exc:
                    logger(f"  WARNING: Failed to open WhatsApp session: {exc}")
                    print_exc()
                    if not continuous:
                        raise
                    sleep_fn(poll_seconds)
                    continue

            logger(
                f"\nSending next {deal.get('lane', 'normal')} deal: "
                f"{deal.get('title', '')[:60]}..."
            )
            attempt_result = send_deal_in_open_chat_fn(
                session["page"],
                deal,
                delay_between=5.0,
                max_retries=2,
            )

            refreshed_queue = prune_expired_entries_fn(load_deal_queue_fn(), now=now_fn())
            if attempt_result["success"]:
                remove_entry_by_offer_key_fn(refreshed_queue, deal["offer_key"])
                sent_data = load_sent_deals_fn()
                mark_deals_as_sent_fn([deal], sent_data=sent_data, auto_save=True)
                results["sent"] += 1
            else:
                mark_deal_failed_fn(refreshed_queue, deal["offer_key"], now=now_fn())
                results["failed"] += 1
                results["errors"].append(
                    {
                        "title": attempt_result["title"],
                        "url": attempt_result["url"],
                        "reason": attempt_result["reason"],
                    }
                )

            mark_sender_tick_fn(refreshed_queue, now_fn())
            save_deal_queue_fn(refreshed_queue)

            if max_messages is not None and results["sent"] + results["failed"] >= max_messages:
                break

            if not continuous:
                continue

        return results
    finally:
        close_whatsapp_session_fn(session)
