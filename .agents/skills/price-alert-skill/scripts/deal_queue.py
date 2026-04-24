#!/usr/bin/env python3

"""Persistent queue helpers for cadence-based deal delivery."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from deal_selection import CADENCE_CONFIG, is_better_deal


ROOT = Path(__file__).resolve().parents[1]
DEAL_QUEUE_FILE = ROOT / "data" / "deal_queue.json"


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
        "normal": [],
        "urgent_retry": [],
        "meta": {
            "last_scan_at": None,
            "last_batch_at": None,
        },
    }


def load_deal_queue() -> dict[str, Any]:
    """Load the persisted cadence queue from disk."""
    if not DEAL_QUEUE_FILE.exists():
        return _default_queue()

    data = json.loads(DEAL_QUEUE_FILE.read_text(encoding="utf-8"))
    queue = _default_queue()
    queue["normal"] = list(data.get("normal", []))
    queue["urgent_retry"] = list(data.get("urgent_retry", []))
    queue["meta"].update(data.get("meta", {}))
    return queue


def save_deal_queue(queue: dict[str, Any]) -> None:
    """Persist the cadence queue to disk."""
    DEAL_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEAL_QUEUE_FILE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_queue_entry(
    deal: dict[str, Any],
    now: datetime | str | None = None,
    *,
    queue_kind: str,
) -> dict[str, Any]:
    now_iso = _to_iso(now)
    entry = dict(deal)
    entry["queue_kind"] = queue_kind
    entry["dedup_key"] = entry.get("dedup_key") or entry.get("offer_key") or entry.get("url")
    entry["first_seen_at"] = entry.get("first_seen_at") or now_iso
    entry["last_seen_at"] = now_iso
    entry["retry_count"] = int(entry.get("retry_count", 0))
    return entry


def _find_offer_index(entries: list[dict[str, Any]], offer_key: str) -> int | None:
    for index, entry in enumerate(entries):
        if entry.get("offer_key") == offer_key:
            return index
    return None


def _find_product_index(entries: list[dict[str, Any]], product_key: str) -> int | None:
    for index, entry in enumerate(entries):
        if entry.get("product_key") == product_key:
            return index
    return None


def enqueue_or_update_normal(
    queue: dict[str, Any],
    deal: dict[str, Any],
    now: datetime | str | None = None,
) -> str:
    """Insert or refresh a normal deal in the cadence queue."""
    normal_entries = queue.setdefault("normal", [])
    now_iso = _to_iso(now)
    offer_index = _find_offer_index(normal_entries, deal["offer_key"])

    if offer_index is not None:
        existing = normal_entries[offer_index]
        refreshed = _build_queue_entry(
            {
                **existing,
                **deal,
                "first_seen_at": existing.get("first_seen_at") or now_iso,
                "retry_count": existing.get("retry_count", 0),
            },
            now_iso,
            queue_kind="normal",
        )
        normal_entries[offer_index] = refreshed
        return "updated"

    product_index = _find_product_index(normal_entries, deal["product_key"])
    if product_index is not None:
        existing = normal_entries[product_index]
        if is_better_deal(deal, existing):
            replacement = _build_queue_entry(
                {
                    **deal,
                    "first_seen_at": existing.get("first_seen_at") or now_iso,
                    "retry_count": existing.get("retry_count", 0),
                },
                now_iso,
                queue_kind="normal",
            )
            normal_entries[product_index] = replacement
            return "replaced"

        existing["last_seen_at"] = now_iso
        return "kept_existing"

    normal_entries.append(_build_queue_entry(deal, now_iso, queue_kind="normal"))
    return "added"


def enqueue_urgent_retry(
    queue: dict[str, Any],
    deal: dict[str, Any],
    now: datetime | str | None = None,
) -> str:
    """Insert or refresh a failed super-promo deal in the urgent retry queue."""
    urgent_entries = queue.setdefault("urgent_retry", [])
    now_iso = _to_iso(now)
    offer_index = _find_offer_index(urgent_entries, deal["offer_key"])

    if offer_index is not None:
        existing = urgent_entries[offer_index]
        urgent_entries[offer_index] = _build_queue_entry(
            {
                **existing,
                **deal,
                "first_seen_at": existing.get("first_seen_at") or now_iso,
                "retry_count": existing.get("retry_count", 0),
            },
            now_iso,
            queue_kind="urgent_retry",
        )
        return "updated"

    urgent_entries.append(_build_queue_entry(deal, now_iso, queue_kind="urgent_retry"))
    return "added"


def drop_expired_entries(
    queue: dict[str, Any],
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Remove entries that stayed stale longer than the configured TTL."""
    current_time = _parse_iso(_to_iso(now)) or _utc_now()
    normal_cutoff = current_time - timedelta(minutes=CADENCE_CONFIG["normal_ttl_minutes"])
    urgent_cutoff = current_time - timedelta(minutes=CADENCE_CONFIG["super_retry_ttl_minutes"])

    queue["normal"] = [
        entry
        for entry in queue.get("normal", [])
        if (_parse_iso(entry.get("last_seen_at")) or current_time) >= normal_cutoff
    ]
    queue["urgent_retry"] = [
        entry
        for entry in queue.get("urgent_retry", [])
        if (_parse_iso(entry.get("first_seen_at")) or current_time) >= urgent_cutoff
    ]
    return queue


def remove_entries_by_offer_keys(queue: dict[str, Any], offer_keys: set[str]) -> dict[str, Any]:
    """Remove successful entries from both queue collections."""
    if not offer_keys:
        return queue

    queue["normal"] = [
        entry for entry in queue.get("normal", [])
        if entry.get("offer_key") not in offer_keys
    ]
    queue["urgent_retry"] = [
        entry for entry in queue.get("urgent_retry", [])
        if entry.get("offer_key") not in offer_keys
    ]
    return queue


def increment_retry_count(
    queue: dict[str, Any],
    offer_keys: set[str],
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Increment retry counters for failed queue entries and drop exhausted ones."""
    now_iso = _to_iso(now)
    normal_max = int(CADENCE_CONFIG["normal_max_retries"])
    super_max = int(CADENCE_CONFIG["super_max_retries"])

    updated_normal = []
    for entry in queue.get("normal", []):
        if entry.get("offer_key") in offer_keys:
            entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
            entry["last_seen_at"] = now_iso
        if int(entry.get("retry_count", 0)) <= normal_max:
            updated_normal.append(entry)
    queue["normal"] = updated_normal

    updated_urgent = []
    for entry in queue.get("urgent_retry", []):
        if entry.get("offer_key") in offer_keys:
            entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
            entry["last_seen_at"] = now_iso
        if int(entry.get("retry_count", 0)) <= super_max:
            updated_urgent.append(entry)
    queue["urgent_retry"] = updated_urgent

    return queue


def mark_scan_run(queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
    """Update queue metadata after a scan cycle."""
    queue.setdefault("meta", {})["last_scan_at"] = _to_iso(now)
    return queue


def mark_batch_run(queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
    """Update queue metadata after a batch dispatch cycle."""
    queue.setdefault("meta", {})["last_batch_at"] = _to_iso(now)
    return queue
