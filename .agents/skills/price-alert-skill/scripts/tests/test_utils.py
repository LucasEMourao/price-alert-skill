"""Tests for utils.py shared utilities."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from utils import (
    calculate_discount,
    deal_fingerprint,
    detect_category_emoji,
    filter_new_deals,
    format_deal_message,
    format_price_brl,
    load_sent_deals,
    save_sent_deals,
)


class TestFormatPriceBrl:
    def test_whole_number(self):
        assert format_price_brl(1500.0) == "R$ 1.500,00"

    def test_with_cents(self):
        assert format_price_brl(89.90) == "R$ 89,90"

    def test_small_amount(self):
        assert format_price_brl(9.99) == "R$ 9,99"

    def test_large_amount(self):
        assert format_price_brl(12345.67) == "R$ 12.345,67"

    def test_zero(self):
        assert format_price_brl(0.0) == "R$ 0,00"


class TestCalculateDiscount:
    def test_basic_discount(self):
        assert calculate_discount(1500.0, 2000.0) == 25.0

    def test_no_discount_when_equal(self):
        assert calculate_discount(1000.0, 1000.0) is None

    def test_no_discount_when_current_higher(self):
        assert calculate_discount(1200.0, 1000.0) is None

    def test_small_discount(self):
        result = calculate_discount(990.0, 1000.0)
        assert result == 1.0

    def test_rounded_result(self):
        result = calculate_discount(1537.50, 2050.0)
        assert result == 25.0


class TestDetectCategoryEmoji:
    def test_mouse(self):
        assert detect_category_emoji("Mouse Gamer Logitech", "mouse gamer") == "🖱️"

    def test_teclado(self):
        assert detect_category_emoji("Teclado Mecanico Redragon", "teclado gamer") == "⌨️"

    def test_headset(self):
        assert detect_category_emoji("Headset HyperX Cloud", "headset gamer") == "🎧"

    def test_monitor(self):
        assert detect_category_emoji("Monitor Gamer 144hz", "monitor gamer") == "🖥️"

    def test_ssd(self):
        assert detect_category_emoji("SSD NVMe 2TB Kingston", "ssd 2tb") == "💾"

    def test_memoria_ram(self):
        assert detect_category_emoji("Memoria RAM DDR5 32GB", "memoria ram ddr5") == "🧩"

    def test_placa_video(self):
        assert detect_category_emoji("Placa de Video RTX 4060", "placa de video rtx") == "🎮"

    def test_notebook(self):
        assert detect_category_emoji("Notebook Gamer Acer", "notebook gamer") == "💻"

    def test_default_emoji(self):
        assert detect_category_emoji("Produto Generico", "generico") == "🎮"

    def test_query_fallback(self):
        assert detect_category_emoji("Produto sem keyword", "mouse gamer") == "🖱️"


class TestFormatDealMessage:
    def test_message_with_discount(self):
        deal = {
            "title": "Mouse Gamer Logitech G203",
            "current_price": 149.90,
            "url": "https://example.com/product",
            "discount_pct": 25.0,
            "previous_price": 199.90,
            "image_url": None,
            "query": "mouse gamer",
        }
        msg = format_deal_message(deal)

        assert "OFERTA DO DIA" in msg
        assert "Mouse Gamer Logitech G203" in msg
        assert "💰 Antes: R$ 199,90" in msg
        assert "🎯 Hoje: R$ 149,90" in msg
        assert "🔥 25% OFF" in msg
        assert "https://example.com/product" in msg

    def test_message_without_discount(self):
        deal = {
            "title": "Produto sem desconto anterior",
            "current_price": 99.90,
            "url": "https://example.com/product",
            "discount_pct": None,
            "previous_price": None,
            "image_url": None,
            "query": "generico",
        }
        msg = format_deal_message(deal)

        assert "🎯 Hoje: R$ 99,90" in msg
        assert "Antes:" not in msg
        assert "% OFF" not in msg

    def test_message_without_image_url_in_text(self):
        deal = {
            "title": "Produto com imagem",
            "current_price": 50.0,
            "url": "https://example.com/product",
            "discount_pct": None,
            "previous_price": None,
            "image_url": "https://example.com/image.jpg",
            "query": "generico",
        }
        msg = format_deal_message(deal)

        assert "📷 Imagem do produto:" not in msg
        assert "https://example.com/image.jpg" not in msg

    def test_long_title_truncated(self):
        deal = {
            "title": "A" * 150,
            "current_price": 100.0,
            "url": "https://example.com/product",
            "discount_pct": None,
            "previous_price": None,
            "image_url": None,
            "query": "generico",
        }
        msg = format_deal_message(deal)

        lines = msg.split("\n")
        title_line = [l for l in lines if l.startswith("🎮") and len(l) > 20][0]
        assert len(title_line) <= 122

    def test_footer_present(self):
        deal = {
            "title": "Teste",
            "current_price": 100.0,
            "url": "https://example.com/product",
            "discount_pct": None,
            "previous_price": None,
            "image_url": None,
            "query": "generico",
        }
        msg = format_deal_message(deal)

        assert "🛍️ Comprar aqui:" in msg
        assert "Valores podem variar" in msg


class TestDealFingerprint:
    def test_same_url_same_price(self):
        deal1 = {"url": "https://example.com/p1", "current_price": 100.0}
        deal2 = {"url": "https://example.com/p1", "current_price": 100.0}
        assert deal_fingerprint(deal1) == deal_fingerprint(deal2)

    def test_same_url_different_price(self):
        deal1 = {"url": "https://example.com/p1", "current_price": 100.0}
        deal2 = {"url": "https://example.com/p1", "current_price": 90.0}
        assert deal_fingerprint(deal1) != deal_fingerprint(deal2)

    def test_different_url_same_price(self):
        deal1 = {"url": "https://example.com/p1", "current_price": 100.0}
        deal2 = {"url": "https://example.com/p2", "current_price": 100.0}
        assert deal_fingerprint(deal1) != deal_fingerprint(deal2)


class TestSentDealsPersistence:
    def test_load_sent_deals_empty(self):
        with patch("utils.SENT_DEALS_FILE", Path("/nonexistent/path.json")):
            data = load_sent_deals()
            assert data == {"sent": {}, "last_cleaned": None}

    def test_save_and_load_sent_deals(self, tmp_path):
        test_file = tmp_path / "sent_deals.json"
        with patch("utils.SENT_DEALS_FILE", test_file):
            data = {"sent": {"https://example.com": "2026-01-01T00:00:00"}, "last_cleaned": None}
            save_sent_deals(data)

            loaded = load_sent_deals()
            assert loaded["sent"]["https://example.com"] == "2026-01-01T00:00:00"


class TestFilterNewDeals:
    def test_all_new_deals(self, tmp_path):
        test_file = tmp_path / "sent_deals.json"
        with patch("utils.SENT_DEALS_FILE", test_file):
            deals = [
                {"url": "https://example.com/p1", "current_price": 100.0},
                {"url": "https://example.com/p2", "current_price": 200.0},
            ]
            new_deals, sent_data = filter_new_deals(deals, auto_save=True)

            assert len(new_deals) == 2
            assert "https://example.com/p1" in sent_data["sent"]
            assert "https://example.com/p2" in sent_data["sent"]

    def test_duplicate_deals_filtered(self, tmp_path):
        from datetime import datetime, timezone
        test_file = tmp_path / "sent_deals.json"
        recent_ts = datetime.now(timezone.utc).isoformat()
        with patch("utils.SENT_DEALS_FILE", test_file):
            existing = {
                "sent": {"https://example.com/p1": recent_ts},
                "last_cleaned": None,
            }
            deals = [
                {"url": "https://example.com/p1", "current_price": 100.0},
                {"url": "https://example.com/p2", "current_price": 200.0},
            ]
            new_deals, sent_data = filter_new_deals(deals, sent_data=existing, auto_save=False)

            assert len(new_deals) == 1
            assert new_deals[0]["url"] == "https://example.com/p2"

    def test_all_duplicates(self, tmp_path):
        from datetime import datetime, timezone
        test_file = tmp_path / "sent_deals.json"
        recent_ts = datetime.now(timezone.utc).isoformat()
        with patch("utils.SENT_DEALS_FILE", test_file):
            existing = {
                "sent": {
                    "https://example.com/p1": recent_ts,
                    "https://example.com/p2": recent_ts,
                },
                "last_cleaned": None,
            }
            deals = [
                {"url": "https://example.com/p1", "current_price": 100.0},
                {"url": "https://example.com/p2", "current_price": 200.0},
            ]
            new_deals, _ = filter_new_deals(deals, sent_data=existing, auto_save=False)

            assert len(new_deals) == 0
