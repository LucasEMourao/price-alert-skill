"""JSON-backed sent-deals repository adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.domain.dedup_policy import (
    build_sent_record,
    can_send_again,
    clean_old_deals,
    deal_offer_key,
    normalize_sent_deals_data,
)


class JSONSentDealsRepository:
    """Persist and query sent-deal history using the existing JSON file format."""

    def __init__(
        self,
        *,
        sent_deals_file_getter: Callable[[], Path],
        cadence_config_getter: Callable[[], dict[str, Any]],
        retention_days_getter: Callable[[], int],
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._sent_deals_file_getter = sent_deals_file_getter
        self._cadence_config_getter = cadence_config_getter
        self._retention_days_getter = retention_days_getter
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def _sent_deals_file(self) -> Path:
        return self._sent_deals_file_getter()

    def _cadence_config(self) -> dict[str, Any]:
        return self._cadence_config_getter()

    def _retention_days(self) -> int:
        return int(self._retention_days_getter())

    def _now(self) -> datetime:
        return self._now_fn()

    def load_sent_deals(self) -> dict[str, Any]:
        """Load sent deals from disk, return empty structure if missing."""
        sent_deals_file = self._sent_deals_file()
        if sent_deals_file.exists():
            raw = json.loads(sent_deals_file.read_text(encoding="utf-8"))
            return normalize_sent_deals_data(raw)
        return {"sent": {}, "last_cleaned": None}

    def save_sent_deals(self, data: dict[str, Any]) -> None:
        """Persist sent deals to disk."""
        sent_deals_file = self._sent_deals_file()
        sent_deals_file.parent.mkdir(parents=True, exist_ok=True)
        sent_deals_file.write_text(
            json.dumps(normalize_sent_deals_data(data), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clean_old_deals(
        self,
        data: dict[str, Any],
        *,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        return clean_old_deals(
            data,
            now=self._now(),
            max_age_days=max_age_days or self._retention_days(),
        )

    def can_send_again(
        self,
        deal: dict[str, Any],
        sent_data: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> bool:
        data = self.clean_old_deals(sent_data or self.load_sent_deals())
        return can_send_again(
            deal,
            data,
            now=now or self._now(),
            cadence_config=self._cadence_config(),
        )

    def filter_new_deals(
        self,
        deals: list[dict[str, Any]],
        sent_data: dict[str, Any] | None = None,
        auto_save: bool = True,
        mark_as_sent: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if sent_data is None:
            sent_data = self.load_sent_deals()

        sent_data = self.clean_old_deals(sent_data)
        new_deals = []
        now_iso = self._now().isoformat()
        now_dt = datetime.fromisoformat(now_iso)

        for deal in deals:
            if self.can_send_again(deal, sent_data, now=now_dt):
                if mark_as_sent:
                    sent_data["sent"][deal_offer_key(deal)] = build_sent_record(deal, sent_at=now_iso)
                new_deals.append(deal)

        if auto_save:
            self.save_sent_deals(sent_data)

        return new_deals, sent_data

    def mark_deals_as_sent(
        self,
        deals: list[dict[str, Any]],
        sent_data: dict[str, Any] | None = None,
        auto_save: bool = True,
    ) -> dict[str, Any]:
        if sent_data is None:
            sent_data = self.load_sent_deals()

        sent_data = self.clean_old_deals(sent_data)
        now_iso = self._now().isoformat()

        for deal in deals:
            sent_data["sent"][deal_offer_key(deal)] = build_sent_record(deal, sent_at=now_iso)

        if auto_save:
            self.save_sent_deals(sent_data)

        return sent_data
