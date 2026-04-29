#!/usr/bin/env python3

"""Persistent pool helpers for the single-sender cadence model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.domain.queue_policy import (
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
from deal_selection import ACTIVE_LANES, CADENCE_CONFIG


ROOT = Path(__file__).resolve().parents[1]
DEAL_QUEUE_FILE = ROOT / "data" / "deal_queue.json"


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
    if not DEAL_QUEUE_FILE.exists():
        return _default_queue()

    data = json.loads(DEAL_QUEUE_FILE.read_text(encoding="utf-8"))
    queue = _default_queue()

    if "urgent_pool" in data or "priority_pool" in data or "normal_pool" in data:
        for lane, pool_key in POOL_KEYS.items():
            queue[pool_key] = [
                _normalize_entry(entry, lane=lane)
                for entry in data.get(pool_key, [])
            ]
    else:
        # Migrate the older queue shape into the new pools.
        queue["urgent_pool"] = [
            _normalize_entry(entry, lane="urgent")
            for entry in data.get("urgent_retry", [])
        ]
        queue["normal_pool"] = [
            _normalize_entry(entry, lane="normal")
            for entry in data.get("normal", [])
        ]

    queue["meta"].update(data.get("meta", {}))
    queue["meta"]["scan_sequence"] = int(queue["meta"].get("scan_sequence", 0) or 0)
    return queue


def save_deal_queue(queue: dict[str, Any]) -> None:
    """Persist the pool state to disk."""
    DEAL_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEAL_QUEUE_FILE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def begin_scan_run(queue: dict[str, Any], now: datetime | str | None = None) -> int:
    """Increment the scan sequence and stamp the latest scan time."""
    return domain_begin_scan_run(queue, now)


def mark_sender_tick(queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
    """Update metadata after a sender processing tick."""
    return domain_mark_sender_tick(queue, now)


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
    return domain_remove_entry_by_offer_key(queue, offer_key)


def remove_entry_by_product_key(queue: dict[str, Any], product_key: str) -> bool:
    """Remove any pooled entry for the given product."""
    return domain_remove_entry_by_product_key(queue, product_key)


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
    return domain_upsert_pool_deal(
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
    return domain_mark_deal_failed(
        queue,
        offer_key,
        now=now,
        retry_backoff_seconds=int(CADENCE_CONFIG["retry_backoff_seconds"]),
        max_send_retries=int(CADENCE_CONFIG["max_send_retries"]),
    )


def prune_expired_entries(
    queue: dict[str, Any],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Drop entries that have fallen out of their freshness windows."""
    return domain_prune_expired_entries(
        queue,
        now=now,
        lane_windows={
            "urgent": (
                int(CADENCE_CONFIG["urgent_window_minutes"]),
                int(CADENCE_CONFIG["urgent_window_scans"]),
            ),
            "priority": (
                int(CADENCE_CONFIG["priority_window_minutes"]),
                int(CADENCE_CONFIG["priority_window_scans"]),
            ),
            "normal": (
                int(CADENCE_CONFIG["normal_window_minutes"]),
                int(CADENCE_CONFIG["normal_window_scans"]),
            ),
        },
    )


def get_sendable_entries(
    queue: dict[str, Any],
    lane: str,
    *,
    now: datetime | str | None = None,
) -> list[dict[str, Any]]:
    """Return pending entries whose retry backoff has elapsed."""
    return domain_get_sendable_entries(queue, lane, now=now)
