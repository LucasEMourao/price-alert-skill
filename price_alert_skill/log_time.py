"""Helpers for rendering user-facing log timestamps in Sao Paulo time."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def to_brazil_log_time(value: datetime) -> datetime:
    """Convert an aware datetime to Sao Paulo time for user-facing logs."""
    if value.tzinfo is None:
        return value.replace(tzinfo=BRAZIL_TZ)
    return value.astimezone(BRAZIL_TZ)


def format_brazil_log_timestamp(value: datetime) -> str:
    """Render a timestamp in the log-friendly Sao Paulo wall-clock format."""
    return to_brazil_log_time(value).strftime("%Y-%m-%d %H:%M:%S")
