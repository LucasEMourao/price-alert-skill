"""Baileys-backed WhatsApp sender adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from price_alert_skill.config import (
    resolve_baileys_gateway_url,
    resolve_whatsapp_group_jid,
)


class BaileysBackendUnavailableError(RuntimeError):
    """Raised when the shared Baileys gateway cannot serve requests."""

    backend_unavailable = True


def _is_backend_unavailable_reason(
    reason: str | None,
    *,
    status_code: int | None = None,
) -> bool:
    normalized = (reason or "").strip().lower()
    if not normalized:
        return bool(status_code and status_code >= 500)

    if normalized.startswith("baileys_not_connected"):
        return True
    if normalized.startswith("baileys_gateway_unreachable"):
        return True
    if normalized.startswith("baileys_gateway_invalid"):
        return True
    if normalized.startswith("baileys gateway request failed:"):
        return True
    if normalized.startswith("gateway_http_5"):
        return True

    return bool(status_code and status_code >= 500)


@dataclass(frozen=True)
class BaileysGatewayClient:
    """Small HTTP client for the local Baileys gateway."""

    gateway_url: str
    group_jid: str
    timeout_seconds: float = 15.0

    def _url(self, path: str) -> str:
        return f"{self.gateway_url.rstrip('/')}/{path.lstrip('/')}"

    def health(self) -> dict[str, Any]:
        try:
            response = requests.get(self._url("/health"), timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BaileysBackendUnavailableError(
                f"baileys_gateway_unreachable:{exc}"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise BaileysBackendUnavailableError(
                "baileys_gateway_invalid_health_response"
            ) from exc

    def send_image(self, *, image_url: str, caption: str) -> dict[str, Any]:
        response = requests.post(
            self._url("/send-image"),
            json={
                "group_jid": self.group_jid,
                "image_url": image_url,
                "caption": caption,
            },
            timeout=self.timeout_seconds,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.ok:
            return payload
        reason = payload.get("reason") or f"gateway_http_{response.status_code}"
        return {
            "success": False,
            "reason": reason,
            "backend_unavailable": _is_backend_unavailable_reason(
                reason,
                status_code=response.status_code,
            ),
        }


class BaileysSessionOpenerAdapter:
    """Open a lightweight Baileys gateway session handle."""

    def __call__(
        self,
        *,
        group_name: str,
        headed: bool,
        reset_session: bool,
    ) -> dict[str, Any]:
        group_jid = resolve_whatsapp_group_jid()
        if not group_jid:
            raise RuntimeError("WHATSAPP_GROUP_JID is required for the Baileys sender backend.")

        client = BaileysGatewayClient(
            gateway_url=resolve_baileys_gateway_url(),
            group_jid=group_jid,
        )
        health = client.health()
        whatsapp_state = health.get("whatsapp", {})
        if not whatsapp_state.get("connected"):
            connection = whatsapp_state.get("connection", "unknown")
            raise BaileysBackendUnavailableError(f"baileys_not_connected:{connection}")

        return {
            "page": client,
            "group_name": group_jid,
            "backend": "baileys",
            "display_group_name": group_name,
            "headed": headed,
            "reset_session": reset_session,
        }


class BaileysSessionCloserAdapter:
    """No-op closer for the shared Baileys gateway."""

    def __call__(self, session: dict[str, Any] | None) -> None:
        return None


class BaileysDealChatSenderAdapter:
    """Send one deal through the local Baileys gateway."""

    def __call__(
        self,
        page: Any,
        deal: dict[str, Any],
        *,
        delay_between: float,
        max_retries: int,
        group_name: str = "",
    ) -> dict[str, Any]:
        title = deal.get("title", "Unknown")
        deal_url = deal.get("url", "")
        dedup_key = deal.get("dedup_key") or deal.get("offer_key") or deal_url
        image_url = deal.get("image_url")
        message = deal.get("message", "")

        if not isinstance(page, BaileysGatewayClient):
            return {
                "success": False,
                "dedup_key": dedup_key,
                "title": title,
                "url": deal_url,
                "reason": "invalid baileys gateway session",
                "backend_unavailable": False,
            }

        if not image_url:
            return {
                "success": False,
                "dedup_key": dedup_key,
                "title": title,
                "url": deal_url,
                "reason": "no image_url",
                "backend_unavailable": False,
            }

        try:
            payload = page.send_image(image_url=image_url, caption=message)
        except requests.RequestException as exc:
            return {
                "success": False,
                "dedup_key": dedup_key,
                "title": title,
                "url": deal_url,
                "reason": f"baileys gateway request failed: {exc}",
                "backend_unavailable": True,
            }

        if payload.get("success"):
            return {
                "success": True,
                "dedup_key": dedup_key,
                "title": title,
                "url": deal_url,
                "message_id": payload.get("message_id"),
            }

        return {
            "success": False,
            "dedup_key": dedup_key,
            "title": title,
            "url": deal_url,
            "reason": payload.get("reason") or "baileys send failed",
            "backend_unavailable": bool(payload.get("backend_unavailable")),
        }
