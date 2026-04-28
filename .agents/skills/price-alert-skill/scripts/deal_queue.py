#!/usr/bin/env python3

"""Persistent pool helpers for the single-sender cadence model."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from deal_selection import ACTIVE_LANES, CADENCE_CONFIG


ROOT = Path(__file__).resolve().parents[1]
DEAL_QUEUE_FILE = ROOT / "data" / "deal_queue.json"

POOL_KEYS = {
    "urgent": "urgent_pool",
    "priority": "priority_pool",
    "normal": "normal_pool",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime | str | None = None) -> str:
    if value is None:
        value = _utc_now()
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _default_queue() -> dict[str, Any]:
    return {
        "urgent_pool": [],
        "priority_pool": [],
        "normal_pool": [],
        "meta": {
            "last_scan_at": None,
            "last_sender_tick_at": None,
            "scan_sequence": 0,
        },
    }


def _normalize_entry(
    entry: dict[str, Any],
    *,
    lane: str,
) -> dict[str, Any]:
    normalized = dict(entry)
    normalized["lane"] = lane
    normalized["queue_kind"] = lane
    normalized["status"] = normalized.get("status", "pending")
    normalized["retry_count"] = int(normalized.get("retry_count", 0))
    normalized["seen_count"] = int(normalized.get("seen_count", 1))
    normalized["first_seen_at"] = normalized.get("first_seen_at")
    normalized["last_seen_at"] = normalized.get("last_seen_at")
    normalized["first_seen_scan"] = int(normalized.get("first_seen_scan", 0) or 0)
    normalized["last_seen_scan"] = int(normalized.get("last_seen_scan", 0) or 0)
    normalized["send_after_at"] = normalized.get("send_after_at")
    normalized["last_send_attempt_at"] = normalized.get("last_send_attempt_at")
    return normalized


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
    meta = queue.setdefault("meta", {})
    next_sequence = int(meta.get("scan_sequence", 0) or 0) + 1
    meta["scan_sequence"] = next_sequence
    meta["last_scan_at"] = _to_iso(now)
    return next_sequence


def mark_sender_tick(queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
    """Update metadata after a sender processing tick."""
    queue.setdefault("meta", {})["last_sender_tick_at"] = _to_iso(now)
    return queue


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
    pool_name, index = _find_offer_location(queue, offer_key)
    if pool_name is None:
        return False
    _remove_at_location(queue, pool_name, index)
    return True


def remove_entry_by_product_key(queue: dict[str, Any], product_key: str) -> bool:
    """Remove any pooled entry for the given product."""
    pool_name, index = _find_product_location(queue, product_key)
    if pool_name is None:
        return False
    _remove_at_location(queue, pool_name, index)
    return True


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
    if lane not in ACTIVE_LANES:
        remove_entry_by_product_key(queue, deal.get("product_key", ""))
        return "discarded"

    scan_sequence = int(scan_sequence or queue.get("meta", {}).get("scan_sequence", 0) or 0)
    now_iso = _to_iso(now)
    target_pool = POOL_KEYS[lane]

    offer_pool, offer_index = _find_offer_location(queue, deal["offer_key"])
    if offer_pool is not None:
        existing = queue[offer_pool][offer_index]
        updated = _build_pool_entry(
            {**existing, **deal},
            lane=lane,
            now_iso=now_iso,
            scan_sequence=scan_sequence,
            first_seen_at=existing.get("first_seen_at"),
            first_seen_scan=existing.get("first_seen_scan"),
            seen_count=int(existing.get("seen_count", 1)) + 1,
            retry_count=int(existing.get("retry_count", 0)),
            last_send_attempt_at=existing.get("last_send_attempt_at"),
            send_after_at=existing.get("send_after_at"),
            status=existing.get("status", "pending"),
        )
        if offer_pool != target_pool:
            _remove_at_location(queue, offer_pool, offer_index)
            queue[target_pool].append(updated)
            return "moved"
        queue[target_pool][offer_index] = updated
        return "updated"

    product_pool, product_index = _find_product_location(queue, deal["product_key"])
    if product_pool is not None:
        existing = queue[product_pool][product_index]
        replacement = _build_pool_entry(
            deal,
            lane=lane,
            now_iso=now_iso,
            scan_sequence=scan_sequence,
            first_seen_at=existing.get("first_seen_at"),
            first_seen_scan=existing.get("first_seen_scan"),
            seen_count=int(existing.get("seen_count", 1)) + 1,
        )
        _remove_at_location(queue, product_pool, product_index)
        queue[target_pool].append(replacement)
        return "replaced_product"

    queue[target_pool].append(
        _build_pool_entry(deal, lane=lane, now_iso=now_iso, scan_sequence=scan_sequence)
    )
    return "added"


def mark_deal_failed(
    queue: dict[str, Any],
    offer_key: str,
    *,
    now: datetime | str | None = None,
) -> bool:
    """Record a send failure and keep the deal pending if it still has retries left."""
    pool_name, index = _find_offer_location(queue, offer_key)
    if pool_name is None:
        return False

    now_dt = _parse_iso(_to_iso(now)) or _utc_now()
    entry = queue[pool_name][index]
    entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
    entry["last_send_attempt_at"] = now_dt.isoformat()
    entry["send_after_at"] = (
        now_dt + timedelta(seconds=CADENCE_CONFIG["retry_backoff_seconds"])
    ).isoformat()
    entry["status"] = "pending"

    if entry["retry_count"] > int(CADENCE_CONFIG["max_send_retries"]):
        _remove_at_location(queue, pool_name, index)
    return True


def prune_expired_entries(
    queue: dict[str, Any],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Drop entries that have fallen out of their freshness windows."""
    now_dt = _parse_iso(_to_iso(now)) or _utc_now()
    scan_sequence = int(queue.get("meta", {}).get("scan_sequence", 0) or 0)
    lane_windows = {
        "urgent": (
            timedelta(minutes=CADENCE_CONFIG["urgent_window_minutes"]),
            int(CADENCE_CONFIG["urgent_window_scans"]),
        ),
        "priority": (
            timedelta(minutes=CADENCE_CONFIG["priority_window_minutes"]),
            int(CADENCE_CONFIG["priority_window_scans"]),
        ),
        "normal": (
            timedelta(minutes=CADENCE_CONFIG["normal_window_minutes"]),
            int(CADENCE_CONFIG["normal_window_scans"]),
        ),
    }

    for lane, pool_name in POOL_KEYS.items():
        time_window, scan_window = lane_windows[lane]
        fresh_entries = []
        for entry in queue.get(pool_name, []):
            last_seen_at = _parse_iso(entry.get("last_seen_at")) or now_dt
            last_seen_scan = int(entry.get("last_seen_scan", scan_sequence) or scan_sequence)
            expired_by_time = last_seen_at < (now_dt - time_window)
            expired_by_scans = last_seen_scan <= max(scan_sequence - scan_window, 0)
            if not expired_by_time and not expired_by_scans:
                fresh_entries.append(entry)
        queue[pool_name] = fresh_entries

    return queue


def get_sendable_entries(
    queue: dict[str, Any],
    lane: str,
    *,
    now: datetime | str | None = None,
) -> list[dict[str, Any]]:
    """Return pending entries whose retry backoff has elapsed."""
    now_dt = _parse_iso(_to_iso(now)) or _utc_now()
    pool_name = POOL_KEYS[lane]
    sendable = []
    for entry in queue.get(pool_name, []):
        send_after = _parse_iso(entry.get("send_after_at"))
        if send_after and send_after > now_dt:
            continue
        sendable.append(entry)
    return sendable
