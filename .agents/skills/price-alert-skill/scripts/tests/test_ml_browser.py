"""Tests for Mercado Livre browser-based fetcher (agent-browser)."""

from unittest.mock import patch

from fetch_ml_browser import (
    _parse_products,
    build_affiliate_url,
    slugify_query,
)


class TestSlugifyQuery:
    def test_spaces_to_hyphens(self):
        assert slugify_query("mouse gamer") == "mouse-gamer"

    def test_multiple_spaces(self):
        assert slugify_query("teclado   mecanico") == "teclado-mecanico"

    def test_special_chars(self):
        assert slugify_query("placa de video") == "placa-de-video"

    def test_uppercase(self):
        assert slugify_query("Mouse GAMER") == "mouse-gamer"


class TestBuildAffiliateUrl:
    @patch("fetch_ml_browser.ML_MATT_WORD", "tb20240811145500")
    @patch("fetch_ml_browser.ML_MATT_TOOL", "21915026")
    def test_builds_affiliate_url(self):
        url = build_affiliate_url("https://www.mercadolivre.com.br/mouse-gamer/p/MLB123456")
        assert "matt_word=tb20240811145500" in url
        assert "matt_tool=21915026" in url

    @patch("fetch_ml_browser.ML_MATT_WORD", "tb20240811145500")
    @patch("fetch_ml_browser.ML_MATT_TOOL", "21915026")
    def test_builds_affiliate_url_with_existing_params(self):
        url = build_affiliate_url(
            "https://www.mercadolivre.com.br/mouse-gamer/p/MLB123?foo=bar"
        )
        assert "foo=bar" in url
        assert "matt_word=tb20240811145500" in url

    @patch("fetch_ml_browser.ML_MATT_WORD", "")
    @patch("fetch_ml_browser.ML_MATT_TOOL", "")
    def test_returns_plain_url_when_no_affiliate_config(self):
        url = build_affiliate_url("https://www.mercadolivre.com.br/mouse-gamer/p/MLB123")
        assert "matt_word" not in url

    def test_returns_none_for_none_input(self):
        assert build_affiliate_url(None) is None


class TestParseProducts:
    def test_parse_single_product(self):
        raw = [
            {
                "title": "Mouse Gamer Redragon Cobra",
                "url": "https://www.mercadolivre.com.br/mouse-gamer-redragon-cobra/p/MLB8752191",
                "currentPriceLabel": "Agora: 112 reais com 49 centavos",
                "listPriceLabel": "Antes: 143 reais",
                "image": "https://http2.mlstatic.com/img.webp",
                "asin": None,
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)

        assert len(products) == 1
        p = products[0]
        assert p["title"] == "Mouse Gamer Redragon Cobra"
        assert p["price"] == 112.49
        assert p["list_price"] == 143.0
        assert "MLB8752191" in (p["url"] or "")

    def test_extracts_mlb_id_from_url(self):
        raw = [
            {
                "title": "Mouse Logitech G203",
                "url": "https://www.mercadolivre.com.br/mouse-logitech/p/MLB16211423",
                "currentPriceLabel": "Agora: 98 reais",
                "listPriceLabel": None,
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)
        assert len(products) == 1
        assert products[0]["asin"] == "MLB16211423"

    def test_skips_empty_title(self):
        raw = [
            {
                "title": "",
                "url": "https://www.mercadolivre.com.br/p/MLB123",
                "currentPriceLabel": "Agora: 50 reais",
                "listPriceLabel": None,
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)
        assert len(products) == 0

    def test_skips_no_url(self):
        raw = [
            {
                "title": "Produto sem URL",
                "url": None,
                "currentPriceLabel": "Agora: 50 reais",
                "listPriceLabel": None,
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)
        assert len(products) == 0

    def test_fallback_url_from_asin(self):
        raw = [
            {
                "title": "Produto com ASIN",
                "url": None,
                "currentPriceLabel": "Agora: 50 reais",
                "listPriceLabel": None,
                "image": None,
                "asin": "MLB12345678",
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)
        assert len(products) == 1
        assert products[0]["url"] is not None
        assert "MLB12345678" in products[0]["url"]

    def test_affiliate_params_appended(self):
        raw = [
            {
                "title": "Mouse Gamer",
                "url": "https://www.mercadolivre.com.br/mouse/p/MLB123",
                "currentPriceLabel": "Agora: 100 reais",
                "listPriceLabel": "Antes: 150 reais",
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
        ]
        with patch("fetch_ml_browser.ML_MATT_WORD", "tb123"), \
             patch("fetch_ml_browser.ML_MATT_TOOL", "456"):
            products = _parse_products(raw)
        assert len(products) == 1
        assert "matt_word=tb123" in products[0]["url"]
        assert "matt_tool=456" in products[0]["url"]

    def test_list_price_parsed(self):
        raw = [
            {
                "title": "Mouse Gamer",
                "url": "https://www.mercadolivre.com.br/mouse/p/MLB123",
                "currentPriceLabel": "Agora: 50 reais com 99 centavos",
                "listPriceLabel": "Antes: 200 reais com 50 centavos",
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
        ]
        products = _parse_products(raw)
        assert products[0]["price"] == 50.99
        assert products[0]["list_price"] == 200.50

    def test_sponsored_flag_preserved(self):
        raw = [
            {
                "title": "Mouse Patrocinado",
                "url": "https://www.mercadolivre.com.br/mouse/p/MLB123",
                "currentPriceLabel": "Agora: 100 reais",
                "listPriceLabel": None,
                "image": None,
                "asin": None,
                "isSponsored": True,
            }
        ]
        products = _parse_products(raw)
        assert products[0]["is_sponsored"] is True

    def test_multiple_products(self):
        raw = [
            {
                "title": f"Produto {i}",
                "url": f"https://www.mercadolivre.com.br/produto/p/MLB{i}",
                "currentPriceLabel": f"Agora: {100 + i} reais",
                "listPriceLabel": None,
                "image": None,
                "asin": None,
                "isSponsored": False,
            }
            for i in range(5)
        ]
        products = _parse_products(raw)
        assert len(products) == 5
