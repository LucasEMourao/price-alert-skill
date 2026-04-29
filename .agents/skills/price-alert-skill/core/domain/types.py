"""Shared domain type aliases for the price-alert skill."""

from __future__ import annotations

from typing import Literal, TypeAlias


Lane: TypeAlias = Literal["discarded", "normal", "priority", "urgent"]
ActiveLane: TypeAlias = Literal["normal", "priority", "urgent"]
QueueStatus: TypeAlias = Literal["pending", "sending", "sent", "failed"]


ALL_LANES: tuple[Lane, ...] = ("discarded", "normal", "priority", "urgent")
ACTIVE_LANES: tuple[ActiveLane, ...] = ("urgent", "priority", "normal")
