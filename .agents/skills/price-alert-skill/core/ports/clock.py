"""Port definitions for time access and sleeping."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Callable contract for producing the current timestamp."""

    def __call__(self) -> Any:
        """Return the current time object used by the application."""


@runtime_checkable
class Sleeper(Protocol):
    """Callable contract for delaying execution."""

    def __call__(self, seconds: float) -> None:
        """Sleep or wait for the given amount of seconds."""
