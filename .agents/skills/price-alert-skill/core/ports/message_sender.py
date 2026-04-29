"""Port definitions for WhatsApp messaging and output formatting."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Logger(Protocol):
    """Callable contract for user-facing log output."""

    def __call__(self, message: str) -> None:
        """Emit a log line."""


@runtime_checkable
class MessageFormatter(Protocol):
    """Callable contract for formatting a deal message."""

    def __call__(self, deal: dict[str, Any]) -> str:
        """Return the formatted message body for the deal."""


@runtime_checkable
class BatchWhatsAppSender(Protocol):
    """Callable contract for batch WhatsApp sends used by the legacy flow."""

    def __call__(
        self,
        *,
        deals: list[dict[str, Any]],
        group_name: str,
        headed: bool,
        reset_session: bool,
    ) -> dict[str, Any]:
        """Send a batch of deals and return the delivery summary."""


@runtime_checkable
class WhatsAppSessionOpener(Protocol):
    """Callable contract for opening a WhatsApp session in the target group."""

    def __call__(
        self,
        *,
        group_name: str,
        headed: bool,
        reset_session: bool,
    ) -> dict[str, Any]:
        """Open the session and return a session payload."""


@runtime_checkable
class WhatsAppSessionCloser(Protocol):
    """Callable contract for closing an opened WhatsApp session."""

    def __call__(self, session: dict[str, Any] | None) -> None:
        """Close the session safely."""


@runtime_checkable
class DealChatSender(Protocol):
    """Callable contract for sending one deal into an already-open WhatsApp chat."""

    def __call__(
        self,
        page: Any,
        deal: dict[str, Any],
        *,
        delay_between: float,
        max_retries: int,
    ) -> dict[str, Any]:
        """Send one deal to the current chat and return the result payload."""
