"""Port definitions for affiliate-link generation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AffiliateLinkGenerator(Protocol):
    """Callable contract for turning product URLs into affiliate URLs."""

    def __call__(self, urls: list[str]) -> dict[str, str]:
        """Return a mapping from original URL to affiliate URL."""
