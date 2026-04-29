"""Port definitions for marketplace scanning and discount extraction helpers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MarketplaceRunner(Protocol):
    """Callable contract for marketplace-specific search execution."""

    def __call__(self, *, query: str, max_results: int) -> dict[str, Any]:
        """Run a marketplace search and return the raw payload."""


@runtime_checkable
class DiscountCalculator(Protocol):
    """Callable contract for turning price pairs into a discount percentage."""

    def __call__(self, current_price: float, list_price: float) -> float | None:
        """Return a percentage discount when it exists."""
