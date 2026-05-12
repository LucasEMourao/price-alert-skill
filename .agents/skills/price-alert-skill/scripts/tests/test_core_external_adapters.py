from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from price_alert_skill.core.adapters.baileys_sender import (
    BaileysDealChatSenderAdapter,
    BaileysGatewayClient,
    BaileysSessionCloserAdapter,
    BaileysSessionOpenerAdapter,
)
from price_alert_skill.core.adapters.meli_affiliate_links import MeliAffiliateLinkGenerator
from price_alert_skill.core.adapters.whatsapp_sender import (
    WhatsAppBatchSender,
    WhatsAppDealChatSenderAdapter,
    WhatsAppSessionCloserAdapter,
    WhatsAppSessionOpenerAdapter,
)
from price_alert_skill.core.ports.affiliate_links import AffiliateLinkGenerator
from price_alert_skill.core.ports.message_sender import (
    BatchWhatsAppSender,
    DealChatSender,
    WhatsAppSessionCloser,
    WhatsAppSessionOpener,
)


def test_meli_affiliate_link_generator_is_port_compatible(monkeypatch):
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.meli_affiliate_links.melila_impl.generate_links",
        lambda urls: {url: f"https://meli.la/{index}" for index, url in enumerate(urls, start=1)},
    )

    adapter = MeliAffiliateLinkGenerator()

    assert isinstance(adapter, AffiliateLinkGenerator)
    assert adapter(["https://example.com/a"]) == {
        "https://example.com/a": "https://meli.la/1"
    }


def test_whatsapp_sender_adapters_are_port_compatible(monkeypatch):
    batch_calls = []
    opener_calls = []
    closer_calls = []
    chat_calls = []

    monkeypatch.setattr(
        "price_alert_skill.core.adapters.whatsapp_sender.whatsapp_impl.send_deals_to_whatsapp",
        lambda **kwargs: batch_calls.append(kwargs) or {"sent": 1, "failed": 0, "errors": []},
    )
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.whatsapp_sender.whatsapp_impl.open_whatsapp_session",
        lambda **kwargs: opener_calls.append(kwargs) or {"page": object()},
    )
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.whatsapp_sender.whatsapp_impl.close_whatsapp_session",
        lambda session: closer_calls.append(session),
    )
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.whatsapp_sender.whatsapp_impl.send_deal_in_open_chat",
        lambda page, deal, *, delay_between, max_retries: chat_calls.append(
            {
                "page": page,
                "deal": deal,
                "delay_between": delay_between,
                "max_retries": max_retries,
            }
        ) or {"success": True, "title": deal["title"], "url": deal["url"]},
    )

    batch_adapter = WhatsAppBatchSender()
    opener_adapter = WhatsAppSessionOpenerAdapter()
    closer_adapter = WhatsAppSessionCloserAdapter()
    chat_adapter = WhatsAppDealChatSenderAdapter()

    assert isinstance(batch_adapter, BatchWhatsAppSender)
    assert isinstance(opener_adapter, WhatsAppSessionOpener)
    assert isinstance(closer_adapter, WhatsAppSessionCloser)
    assert isinstance(chat_adapter, DealChatSender)

    batch_result = batch_adapter(
        deals=[{"title": "Deal"}],
        group_name="Grupo",
        headed=False,
        reset_session=False,
    )
    session = opener_adapter(group_name="Grupo", headed=False, reset_session=False)
    closer_adapter(session)
    chat_result = chat_adapter(
        object(),
        {"title": "Deal", "url": "https://example.com"},
        delay_between=5.0,
        max_retries=2,
    )

    assert batch_result["sent"] == 1
    assert batch_calls[0]["group_name"] == "Grupo"
    assert "page" in session
    assert opener_calls[0]["group_name"] == "Grupo"
    assert closer_calls == [session]
    assert chat_result["success"] is True
    assert chat_calls[0]["delay_between"] == 5.0
    assert chat_calls[0]["max_retries"] == 2



class _FakeResponse:
    def __init__(self, payload, *, ok=True, status_code=200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"http {self.status_code}")


def test_baileys_sender_adapters_are_port_compatible():
    opener_adapter = BaileysSessionOpenerAdapter()
    closer_adapter = BaileysSessionCloserAdapter()
    chat_adapter = BaileysDealChatSenderAdapter()

    assert isinstance(opener_adapter, WhatsAppSessionOpener)
    assert isinstance(closer_adapter, WhatsAppSessionCloser)
    assert isinstance(chat_adapter, DealChatSender)


def test_baileys_deal_sender_posts_image(monkeypatch):
    posts = []

    def fake_post(url, *, json, timeout):
        posts.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse({"success": True, "message_id": "msg-1"})

    monkeypatch.setattr(
        "price_alert_skill.core.adapters.baileys_sender.requests.post",
        fake_post,
    )

    client = BaileysGatewayClient(
        gateway_url="http://gateway.local",
        group_jid="120363@g.us",
    )
    result = BaileysDealChatSenderAdapter()(
        client,
        {
            "title": "Deal",
            "url": "https://example.com/deal",
            "dedup_key": "offer-1",
            "image_url": "https://example.com/image.jpg",
            "message": "Caption",
        },
        delay_between=5.0,
        max_retries=2,
    )

    assert result["success"] is True
    assert result["message_id"] == "msg-1"
    assert posts[0]["url"] == "http://gateway.local/send-image"
    assert posts[0]["json"]["group_jid"] == "120363@g.us"
    assert posts[0]["json"]["image_url"] == "https://example.com/image.jpg"
    assert posts[0]["json"]["caption"] == "Caption"


def test_baileys_deal_sender_reports_gateway_error(monkeypatch):
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.baileys_sender.requests.post",
        lambda *args, **kwargs: _FakeResponse(
            {"success": False, "reason": "baileys_not_connected"},
            ok=False,
            status_code=409,
        ),
    )

    client = BaileysGatewayClient(
        gateway_url="http://gateway.local",
        group_jid="120363@g.us",
    )
    result = BaileysDealChatSenderAdapter()(
        client,
        {
            "title": "Deal",
            "url": "https://example.com/deal",
            "image_url": "https://example.com/image.jpg",
            "message": "Caption",
        },
        delay_between=5.0,
        max_retries=2,
    )

    assert result["success"] is False
    assert result["reason"] == "baileys_not_connected"


def test_baileys_session_opener_requires_group_jid(monkeypatch):
    monkeypatch.setattr(
        "price_alert_skill.core.adapters.baileys_sender.resolve_whatsapp_group_jid",
        lambda: "",
    )

    try:
        BaileysSessionOpenerAdapter()(group_name="", headed=False, reset_session=False)
    except RuntimeError as exc:
        assert "WHATSAPP_GROUP_JID" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
