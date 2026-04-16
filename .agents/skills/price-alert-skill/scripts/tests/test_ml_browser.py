"""Tests for Mercado Livre browser-based fetcher (Playwright)."""

from fetch_ml_browser import (
    _parse_products,
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
