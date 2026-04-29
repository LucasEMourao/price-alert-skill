"""Port definitions for queue persistence and queue-state operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class QueueRepository(Protocol):
    """Contract for loading, saving, and mutating the sender queue state."""

    def load_deal_queue(self) -> dict[str, Any]:
        """Load the current queue state."""

    def save_deal_queue(self, queue: dict[str, Any]) -> None:
        """Persist the current queue state."""

    def begin_scan_run(self, queue: dict[str, Any], now: datetime | str | None = None) -> int:
        """Start a new scan run and advance queue metadata."""

    def mark_sender_tick(self, queue: dict[str, Any], now: datetime | str | None = None) -> dict[str, Any]:
        """Stamp queue metadata after a sender tick."""

    def prune_expired_entries(
        self,
        queue: dict[str, Any],
        *,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Drop entries outside their freshness windows."""

    def upsert_pool_deal(
        self,
        queue: dict[str, Any],
        deal: dict[str, Any],
        lane: str,
        *,
        now: datetime | str | None = None,
        scan_sequence: int | None = None,
    ) -> str:
        """Insert or refresh a deal in a lane pool."""

    def remove_entry_by_product_key(self, queue: dict[str, Any], product_key: str) -> bool:
        """Remove any pooled entry for the given product."""

    def remove_entry_by_offer_key(self, queue: dict[str, Any], offer_key: str) -> bool:
        """Remove a specific pooled offer."""

    def get_sendable_entries(
        self,
        queue: dict[str, Any],
        lane: str,
        *,
        now: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        """Return entries whose backoff has elapsed."""

    def mark_deal_failed(
        self,
        queue: dict[str, Any],
        offer_key: str,
        *,
        now: datetime | str | None = None,
    ) -> bool:
        """Record a send failure and update retry/backoff state."""
