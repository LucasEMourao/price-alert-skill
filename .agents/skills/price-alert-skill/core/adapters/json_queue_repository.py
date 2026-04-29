"""JSON-backed queue repository adapter."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.domain.queue_policy import (
    POOL_KEYS,
    begin_scan_run,
    default_queue,
    get_sendable_entries,
    mark_deal_failed,
    mark_sender_tick,
    normalize_entry,
    prune_expired_entries,
    remove_entry_by_offer_key,
    remove_entry_by_product_key,
    upsert_pool_deal,
)


class JSONQueueRepository:
    """Persist and manipulate queue state using the existing JSON file format."""

    def __init__(
        self,
        *,
        queue_file_getter: Callable[[], Path],
        cadence_config_getter: Callable[[], dict[str, Any]],
    ) -> None:
        self._queue_file_getter = queue_file_getter
        self._cadence_config_getter = cadence_config_getter

    def _queue_file(self) -> Path:
        return self._queue_file_getter()

    def _cadence_config(self) -> dict[str, Any]:
        return self._cadence_config_getter()

    def load_deal_queue(self) -> dict[str, Any]:
        """Load the persisted pools from disk, migrating older queue shapes."""
        queue_file = self._queue_file()
        if not queue_file.exists():
            return default_queue()

        data = json.loads(queue_file.read_text(encoding="utf-8"))
        queue = default_queue()

        if "urgent_pool" in data or "priority_pool" in data or "normal_pool" in data:
            for lane, pool_key in POOL_KEYS.items():
                queue[pool_key] = [
                    normalize_entry(entry, lane=lane)
                    for entry in data.get(pool_key, [])
                ]
        else:
            queue["urgent_pool"] = [
                normalize_entry(entry, lane="urgent")
                for entry in data.get("urgent_retry", [])
            ]
            queue["normal_pool"] = [
                normalize_entry(entry, lane="normal")
                for entry in data.get("normal", [])
            ]

        queue["meta"].update(data.get("meta", {}))
        queue["meta"]["scan_sequence"] = int(queue["meta"].get("scan_sequence", 0) or 0)
        return queue

    def save_deal_queue(self, queue: dict[str, Any]) -> None:
        """Persist the pool state to disk."""
        queue_file = self._queue_file()
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def begin_scan_run(self, queue: dict[str, Any], now: datetime | str | None = None) -> int:
        return begin_scan_run(queue, now)

    def mark_sender_tick(
        self,
        queue: dict[str, Any],
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        return mark_sender_tick(queue, now)

    def upsert_pool_deal(
        self,
        queue: dict[str, Any],
        deal: dict[str, Any],
        lane: str,
        *,
        now: datetime | str | None = None,
        scan_sequence: int | None = None,
    ) -> str:
        return upsert_pool_deal(
            queue,
            deal,
            lane,
            now=now,
            scan_sequence=scan_sequence,
        )

    def remove_entry_by_product_key(self, queue: dict[str, Any], product_key: str) -> bool:
        return remove_entry_by_product_key(queue, product_key)

    def remove_entry_by_offer_key(self, queue: dict[str, Any], offer_key: str) -> bool:
        return remove_entry_by_offer_key(queue, offer_key)

    def prune_expired_entries(
        self,
        queue: dict[str, Any],
        *,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        cadence_config = self._cadence_config()
        return prune_expired_entries(
            queue,
            now=now,
            lane_windows={
                "urgent": (
                    int(cadence_config["urgent_window_minutes"]),
                    int(cadence_config["urgent_window_scans"]),
                ),
                "priority": (
                    int(cadence_config["priority_window_minutes"]),
                    int(cadence_config["priority_window_scans"]),
                ),
                "normal": (
                    int(cadence_config["normal_window_minutes"]),
                    int(cadence_config["normal_window_scans"]),
                ),
            },
        )

    def get_sendable_entries(
        self,
        queue: dict[str, Any],
        lane: str,
        *,
        now: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        return get_sendable_entries(queue, lane, now=now)

    def mark_deal_failed(
        self,
        queue: dict[str, Any],
        offer_key: str,
        *,
        now: datetime | str | None = None,
    ) -> bool:
        cadence_config = self._cadence_config()
        return mark_deal_failed(
            queue,
            offer_key,
            now=now,
            retry_backoff_seconds=int(cadence_config["retry_backoff_seconds"]),
            max_send_retries=int(cadence_config["max_send_retries"]),
        )
