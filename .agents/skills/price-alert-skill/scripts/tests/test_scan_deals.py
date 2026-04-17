#!/usr/bin/env python3

"""Tests for scan_deals WhatsApp group resolution."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import scan_deals


def _sample_deal() -> dict:
    return {
        "title": "Mouse Gamer",
        "url": "https://example.com/product",
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

    @patch("send_to_whatsapp.send_deals_to_whatsapp", return_value={"sent": 1, "failed": 0, "errors": []})
    def test_main_uses_env_group_when_flag_is_missing(self, mock_send, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [_sample_deal()])
        monkeypatch.setattr(scan_deals, "filter_new_deals", lambda deals, auto_save=True: (deals, {"sent": {}}))
        monkeypatch.setattr(scan_deals, "format_deal_message", lambda deal: "Mensagem formatada")
        monkeypatch.setattr(
            sys,
            "argv",
            ["scan_deals.py", "--all", "--send-whatsapp", "--output", str(tmp_path / "deals.json")],
        )

        scan_deals.main()

        assert mock_send.call_args.kwargs["group_name"] == "Grupo via Env"

    @patch("send_to_whatsapp.send_deals_to_whatsapp", return_value={"sent": 1, "failed": 0, "errors": []})
    def test_main_prefers_cli_group_over_env(self, mock_send, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(scan_deals, "scan_all", lambda *args, **kwargs: [_sample_deal()])
        monkeypatch.setattr(scan_deals, "filter_new_deals", lambda deals, auto_save=True: (deals, {"sent": {}}))
        monkeypatch.setattr(scan_deals, "format_deal_message", lambda deal: "Mensagem formatada")
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

        assert mock_send.call_args.kwargs["group_name"] == "Grupo via CLI"
