#!/usr/bin/env python3

"""Persistent pool helpers for the single-sender cadence model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from price_alert_skill.core.adapters.json_queue_repository import JSONQueueRepository
from price_alert_skill.core.domain.queue_policy import (
    POOL_KEYS,
    begin_scan_run as domain_begin_scan_run,
    default_queue as domain_default_queue,
    get_sendable_entries as domain_get_sendable_entries,
    mark_deal_failed as domain_mark_deal_failed,
    mark_sender_tick as domain_mark_sender_tick,
    normalize_entry as domain_normalize_entry,
    parse_iso as domain_parse_iso,
    prune_expired_entries as domain_prune_expired_entries,
    remove_entry_by_offer_key as domain_remove_entry_by_offer_key,
    remove_entry_by_product_key as domain_remove_entry_by_product_key,
    to_iso as domain_to_iso,
    upsert_pool_deal as domain_upsert_pool_deal,
    utc_now as domain_utc_now,
)
from price_alert_skill.deal_selection import ACTIVE_LANES, CADENCE_CONFIG
from price_alert_skill.paths import resolve_data_dir


DEAL_QUEUE_FILE = resolve_data_dir() / "deal_queue.json"
_QUEUE_REPOSITORY = JSONQueueRepository(
    queue_file_getter=lambda: DEAL_QUEUE_FILE,
    cadence_config_getter=lambda: CADENCE_CONFIG,
)


def _utc_now() -> datetime:
    return domain_utc_now()


def _to_iso(value: datetime | str | None = None) -> str:
    return domain_to_iso(value)


def _parse_iso(value: str | None) -> datetime | None:
    return domain_parse_iso(value)


def _default_queue() -> dict[str, Any]:
    return domain_default_queue()


def _normalize_entry(
    entry: dict[str, Any],
    *,
    lane: str,
) -> dict[str, Any]:
    return domain_normalize_entry(entry, lane=lane)


def load_deal_queue() -> dict[str, Any]:
    """Load the persisted pools from disk, migrating older queue shapes."""
    return _QUEUE_REPOSITORY.load_deal_queue()


def save_deal_queue(queue: dict[str, Any]) -> None:
    """Persist the pool state to disk."""
    _QUEUE_REPOSITORY.save_deal_queue(queue)


def begin_scan_run(queue: dict[str, Any], now: datetime | str | None = None) -> int:
    """Increment the scan sequence and stamp the latest scan time."""
    return _QUEUE_REPOSITORY.begin_scan_run(queue, now)


def mark_sender_tick(queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
    """Update metadata after a sender processing tick."""
    return _QUEUE_REPOSITORY.mark_sender_tick(queue, now)


def _iter_pool_names() -> tuple[str, ...]:
    return tuple(POOL_KEYS.values())


def _find_offer_location(queue: dict[str, Any], offer_key: str) -> tuple[str, int] | tuple[None, None]:
    for pool_name in _iter_pool_names():
        for index, entry in enumerate(queue.get(pool_name, [])):
            if entry.get("offer_key") == offer_key:
                return pool_name, index
    return None, None


def _find_product_location(
    queue: dict[str, Any],
    product_key: str,
) -> tuple[str, int] | tuple[None, None]:
    for pool_name in _iter_pool_names():
        for index, entry in enumerate(queue.get(pool_name, [])):
            if entry.get("product_key") == product_key:
                return pool_name, index
    return None, None


def _remove_at_location(queue: dict[str, Any], pool_name: str | None, index: int | None) -> None:
    if pool_name is None or index is None:
        return
    queue.get(pool_name, []).pop(index)


def remove_entry_by_offer_key(queue: dict[str, Any], offer_key: str) -> bool:
    """Remove a specific offer from the pools."""
    return _QUEUE_REPOSITORY.remove_entry_by_offer_key(queue, offer_key)


def remove_entry_by_product_key(queue: dict[str, Any], product_key: str) -> bool:
    """Remove any pooled entry for the given product."""
    return _QUEUE_REPOSITORY.remove_entry_by_product_key(queue, product_key)


def _build_pool_entry(
    deal: dict[str, Any],
    *,
    lane: str,
    now_iso: str,
    scan_sequence: int,
    first_seen_at: str | None = None,
    first_seen_scan: int | None = None,
    seen_count: int = 1,
    retry_count: int = 0,
    last_send_attempt_at: str | None = None,
    send_after_at: str | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    entry = dict(deal)
    entry["lane"] = lane
    entry["queue_kind"] = lane
    entry["status"] = status
    entry["first_seen_at"] = first_seen_at or now_iso
    entry["last_seen_at"] = now_iso
    entry["first_seen_scan"] = int(first_seen_scan or scan_sequence)
    entry["last_seen_scan"] = int(scan_sequence)
    entry["seen_count"] = int(seen_count)
    entry["retry_count"] = int(retry_count)
    entry["last_send_attempt_at"] = last_send_attempt_at
    entry["send_after_at"] = send_after_at
    return entry


def upsert_pool_deal(
    queue: dict[str, Any],
    deal: dict[str, Any],
    lane: str,
    *,
    now: datetime | str | None = None,
    scan_sequence: int | None = None,
) -> str:
    """Insert or refresh a deal in the target lane pool."""
    return _QUEUE_REPOSITORY.upsert_pool_deal(
        queue,
        deal,
        lane,
        now=now,
        scan_sequence=scan_sequence,
    )


def mark_deal_failed(
    queue: dict[str, Any],
    offer_key: str,
    *,
    now: datetime | str | None = None,
) -> bool:
    """Record a send failure and keep the deal pending if it still has retries left."""
    return _QUEUE_REPOSITORY.mark_deal_failed(
        queue,
        offer_key,
        now=now,
    )


def prune_expired_entries(
    queue: dict[str, Any],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Drop entries that have fallen out of their freshness windows."""
    return _QUEUE_REPOSITORY.prune_expired_entries(queue, now=now)


def get_sendable_entries(
    queue: dict[str, Any],
    lane: str,
    *,
    now: datetime | str | None = None,
) -> list[dict[str, Any]]:
    """Return pending entries whose retry backoff has elapsed."""
    return _QUEUE_REPOSITORY.get_sendable_entries(queue, lane, now=now)
