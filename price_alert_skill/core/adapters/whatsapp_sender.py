"""Concrete WhatsApp sender adapters backed by the existing Playwright module."""

from __future__ import annotations

from typing import Any

from price_alert_skill import send_to_whatsapp as whatsapp_impl


class WhatsAppBatchSender:
    """Batch sender adapter used by the legacy scan-and-send flow."""

    def __call__(
        self,
        *,
        deals: list[dict[str, Any]],
        group_name: str,
        headed: bool,
        reset_session: bool,
    ) -> dict[str, Any]:
        return whatsapp_impl.send_deals_to_whatsapp(
            deals=deals,
            group_name=group_name,
            headed=headed,
            reset_session=reset_session,
        )


class WhatsAppSessionOpenerAdapter:
    """Open a persistent WhatsApp session in the target group."""

    def __call__(
        self,
        *,
        group_name: str,
        headed: bool,
        reset_session: bool,
    ) -> dict[str, Any]:
        return whatsapp_impl.open_whatsapp_session(
            group_name=group_name,
            headed=headed,
            reset_session=reset_session,
        )


class WhatsAppSessionCloserAdapter:
    """Close a session previously opened through the adapter."""

    def __call__(self, session: dict[str, Any] | None) -> None:
        whatsapp_impl.close_whatsapp_session(session)


class WhatsAppDealChatSenderAdapter:
    """Send a single deal to an already-open WhatsApp chat."""

    def __call__(
        self,
        page: Any,
        deal: dict[str, Any],
        *,
        delay_between: float,
        max_retries: int,
    ) -> dict[str, Any]:
        return whatsapp_impl.send_deal_in_open_chat(
            page,
            deal,
            delay_between=delay_between,
            max_retries=max_retries,
        )
