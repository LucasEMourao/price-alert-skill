"""Tests for Mercado Livre BR fetcher parser."""

from unittest.mock import patch

from fetch_mercadolivre_br import (
    build_affiliate_url,
    extract_products_from_html,
    parse_brl_from_label,
    slugify_query,
)


class TestParseBrlFromLabel:
    def test_reais_and_centavos(self):
        assert parse_brl_from_label("206 reais com 64 centavos") == 206.64

    def test_reais_only(self):
        assert parse_brl_from_label("299 reais") == 299.0

    def test_single_digit_centavos(self):
        assert parse_brl_from_label("50 reais com 5 centavos") == 50.05

    def test_none_input(self):
        assert parse_brl_from_label(None) is None

    def test_empty_string(self):
        assert parse_brl_from_label("") is None

    def test_case_insensitive(self):
        assert parse_brl_from_label("100 Reais com 50 Centavos") == 100.50


class TestSlugifyQuery:
    def test_spaces_to_hyphens(self):
        assert slugify_query("mouse gamer") == "mouse-gamer"

    def test_multiple_spaces(self):
        assert slugify_query("teclado   mecanico") == "teclado-mecanico"

    def test_special_chars(self):
        assert slugify_query("placa de video") == "placa-de-video"

    def test_already_slug(self):
        assert slugify_query("mouse-gamer") == "mouse-gamer"

    def test_uppercase(self):
        assert slugify_query("Mouse GAMER") == "mouse-gamer"


class TestExtractProductsFromHtml:
    def test_extract_single_product(self):
        html = """
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Mouse Gamer Logitech G203</h2>
            <img class="poly-component__picture" src="https://example.com/img.jpg" />
            <span aria-label="Agora: 149 reais com 90 centavos"></span>
            <span aria-label="Antes: 199 reais"></span>
            <span>MLB12345678</span>
        </div>
        """
        products = extract_products_from_html(html, max_results=5)

        assert len(products) == 1
        product = products[0]
        assert product["title"] == "Mouse Gamer Logitech G203"
        assert product["price"] == 149.90
        assert product["list_price"] == 199.0
        assert product["image_url"] == "https://example.com/img.jpg"
        assert product["url"] == "https://produto.mercadolivre.com.br/MLB-12345678-_JM"

    def test_extract_product_without_list_price(self):
        html = """
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Produto sem desconto</h2>
            <span aria-label="Agora: 100 reais"></span>
            <span>MLB87654321</span>
        </div>
        """
        products = extract_products_from_html(html, max_results=5)

        assert len(products) == 1
        assert products[0]["price"] == 100.0
        assert products[0]["list_price"] is None

    def test_skips_card_without_title(self):
        html = """
        <div class="ui-search-result__wrapper">
            <span aria-label="Agora: 50 reais"></span>
        </div>
        """
        products = extract_products_from_html(html, max_results=5)

        assert len(products) == 0

    def test_respects_max_results(self):
        html = """
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Produto 1</h2>
            <span aria-label="Agora: 100 reais"></span>
            <span>MLB001</span>
        </div>
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Produto 2</h2>
            <span aria-label="Agora: 200 reais"></span>
            <span>MLB002</span>
        </div>
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Produto 3</h2>
            <span aria-label="Agora: 300 reais"></span>
            <span>MLB003</span>
        </div>
        """
        products = extract_products_from_html(html, max_results=2)

        assert len(products) == 2

    def test_detects_sponsored(self):
        html = """
        <div class="ui-search-result__wrapper">
            <h2 class="poly-component__title">Produto Patrocinado</h2>
            <span aria-label="Agora: 100 reais"></span>
            <span>MLB001</span>
            <input type="hidden" value="is_advertising=true" />
        </div>
        """
        products = extract_products_from_html(html, max_results=5)

        assert len(products) == 1
        assert products[0]["is_sponsored"] is True


class TestBuildAffiliateUrl:
    @patch("fetch_mercadolivre_br.ML_MATT_WORD", "tb20240811145500")
    @patch("fetch_mercadolivre_br.ML_MATT_TOOL", "21915026")
    def test_builds_affiliate_url(self):
        url = build_affiliate_url("https://produto.mercadolivre.com.br/MLB-12345678-_JM")
        assert url == "https://produto.mercadolivre.com.br/MLB-12345678-_JM?matt_word=tb20240811145500&matt_tool=21915026"

    @patch("fetch_mercadolivre_br.ML_MATT_WORD", "tb20240811145500")
    @patch("fetch_mercadolivre_br.ML_MATT_TOOL", "21915026")
    def test_builds_affiliate_url_with_existing_params(self):
        url = build_affiliate_url("https://produto.mercadolivre.com.br/MLB-12345678-_JM?some=param")
        assert url == "https://produto.mercadolivre.com.br/MLB-12345678-_JM?some=param&matt_word=tb20240811145500&matt_tool=21915026"

    @patch("fetch_mercadolivre_br.ML_MATT_WORD", "")
    @patch("fetch_mercadolivre_br.ML_MATT_TOOL", "")
    def test_returns_plain_url_when_no_affiliate_config(self):
        url = build_affiliate_url("https://produto.mercadolivre.com.br/MLB-12345678-_JM")
        assert url == "https://produto.mercadolivre.com.br/MLB-12345678-_JM"

    def test_returns_none_for_none_input(self):
        url = build_affiliate_url(None)
        assert url is None
