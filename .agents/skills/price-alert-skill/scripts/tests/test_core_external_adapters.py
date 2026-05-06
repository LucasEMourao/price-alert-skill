from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
