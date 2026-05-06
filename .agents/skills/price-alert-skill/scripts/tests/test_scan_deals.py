#!/usr/bin/env python3

"""Tests for scan_deals WhatsApp group resolution."""

import sys

import price_alert_skill.config as config
from price_alert_skill import scan_deals


def _sample_deal() -> dict:
    return {
        "title": "Mouse Gamer",
        "url": "https://example.com/product",
        "dedup_key": "https://example.com/product",
        "image_url": "https://example.com/product.jpg",
        "marketplace": "amazon_br",
        "current_price": 199.9,
        "current_price_text": "R$ 199,90",
        "previous_price": 249.9,
        "previous_price_text": "R$ 249,90",
        "discount_pct": 20.0,
        "query": "mouse gamer",
    }


class TestScanDealsWhatsappGroup:
    """Tests for resolving the WhatsApp group in scan_deals.py."""

    def test_main_uses_env_group_when_flag_is_missing(self, monkeypatch, tmp_path):
        captured = {}
        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [_sample_deal()])
        monkeypatch.setattr(
            scan_deals,
            "filter_new_deals",
            lambda deals, auto_save=True, mark_as_sent=True: (deals, {"sent": {}}),
        )
        monkeypatch.setattr(scan_deals, "format_deal_message", lambda deal: "Mensagem formatada")
        monkeypatch.setattr(
            scan_deals,
            "_WHATSAPP_BATCH_SENDER",
            lambda **kwargs: captured.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["scan_deals.py", "--all", "--send-whatsapp", "--output", str(tmp_path / "deals.json")],
        )

        scan_deals.main()

        assert captured["group_name"] == "Grupo via Env"

    def test_main_prefers_cli_group_over_env(self, monkeypatch, tmp_path):
        captured = {}
        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [_sample_deal()])
        monkeypatch.setattr(
            scan_deals,
            "filter_new_deals",
            lambda deals, auto_save=True, mark_as_sent=True: (deals, {"sent": {}}),
        )
        monkeypatch.setattr(scan_deals, "format_deal_message", lambda deal: "Mensagem formatada")
        monkeypatch.setattr(
            scan_deals,
            "_WHATSAPP_BATCH_SENDER",
            lambda **kwargs: captured.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scan_deals.py",
                "--all",
                "--send-whatsapp",
                "--whatsapp-group",
                "Grupo via CLI",
                "--output",
                str(tmp_path / "deals.json"),
            ],
        )

        scan_deals.main()

        assert captured["group_name"] == "Grupo via CLI"

    def test_main_marks_only_successful_deals_after_whatsapp_send(self, monkeypatch, tmp_path):
        saved_payload = {}
        sender_calls = {}

        deal = _sample_deal()
        deal["dedup_key"] = "deal-1"

        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [deal])
        monkeypatch.setattr(
            scan_deals,
            "filter_new_deals",
            lambda deals, auto_save=True, mark_as_sent=True: (deals, {"sent": {}}),
        )
        monkeypatch.setattr(scan_deals, "format_deal_message", lambda deal: "Mensagem formatada")
        monkeypatch.setattr(
            scan_deals,
            "mark_deals_as_sent",
            lambda deals, sent_data=None, auto_save=True: saved_payload.update(
                {"deals": deals, "sent_data": sent_data, "auto_save": auto_save}
            ),
        )
        monkeypatch.setattr(
            scan_deals,
            "_WHATSAPP_BATCH_SENDER",
            lambda **kwargs: sender_calls.update(kwargs)
            or {
                "sent": 1,
                "failed": 1,
                "errors": [{"title": "Mouse Gamer", "reason": "send failed"}],
                "successful_keys": [kwargs["deals"][0]["dedup_key"]],
            },
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["scan_deals.py", "--all", "--send-whatsapp", "--output", str(tmp_path / "deals.json")],
        )

        scan_deals.main()

        assert sender_calls["group_name"] == "Grupo via Env"
        assert saved_payload["auto_save"] is True
        assert len(saved_payload["deals"]) == 1
        assert saved_payload["deals"][0]["dedup_key"] == "deal-1"

    def test_scan_only_does_not_send_whatsapp_anymore(self, monkeypatch, tmp_path):
        sender_calls = {}
        deal = _sample_deal()
        deal["current_price"] = 100.0
        deal["current_price_text"] = "R$ 100,00"
        deal["previous_price"] = 200.0
        deal["previous_price_text"] = "R$ 200,00"
        deal["discount_pct"] = 50.0

        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [deal])
        monkeypatch.setattr(scan_deals, "apply_affiliate_links", lambda deals: None)
        monkeypatch.setattr(scan_deals, "load_sent_deals", lambda: {"sent": {}, "last_cleaned": None})
        monkeypatch.setattr(
            scan_deals,
            "load_deal_queue",
            lambda: {
                "urgent_pool": [],
                "priority_pool": [],
                "normal_pool": [],
                "meta": {"last_scan_at": None, "last_sender_tick_at": None, "scan_sequence": 0},
            },
        )
        saved_queue = {}
        monkeypatch.setattr(scan_deals, "save_deal_queue", lambda queue: saved_queue.update(queue))
        monkeypatch.setattr(
            scan_deals,
            "_WHATSAPP_BATCH_SENDER",
            lambda **kwargs: sender_calls.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scan_deals.py",
                "--all",
                "--scan-only",
                "--send-whatsapp",
                "--output",
                str(tmp_path / "deals.json"),
            ],
        )

        scan_deals.main()

        assert sender_calls == {}
        assert saved_queue["normal_pool"] or saved_queue["priority_pool"] or saved_queue["urgent_pool"]
        pooled = saved_queue["normal_pool"] or saved_queue["priority_pool"] or saved_queue["urgent_pool"]
        assert pooled[0]["message"]
