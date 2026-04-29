"""Port definitions for sent-deals persistence and resend policies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SentDealsRepository(Protocol):
    """Contract for dedup history and resend decisions."""

    def load_sent_deals(self) -> dict[str, Any]:
        """Load sent-deal history."""

    def save_sent_deals(self, data: dict[str, Any]) -> None:
        """Persist sent-deal history."""

    def can_send_again(
        self,
        deal: dict[str, Any],
        sent_data: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return whether the deal is eligible to be sent again."""

    def filter_new_deals(
        self,
        deals: list[dict[str, Any]],
        sent_data: dict[str, Any] | None = None,
        auto_save: bool = True,
        mark_as_sent: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Filter deals against sent history."""

    def mark_deals_as_sent(
        self,
        deals: list[dict[str, Any]],
        sent_data: dict[str, Any] | None = None,
        auto_save: bool = True,
    ) -> dict[str, Any]:
        """Record deals as sent after downstream success."""
