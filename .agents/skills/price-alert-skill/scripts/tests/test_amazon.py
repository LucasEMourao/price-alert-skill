"""Tests for Amazon BR fetcher parser."""

import json
from unittest.mock import patch

from price_alert_skill.fetch_amazon_br import (
    AmazonSearchHTMLParser,
    build_affiliate_url,
    normalize_products,
    parse_brl_amount,
    parse_rating,
    parse_review_count,
)


class TestParseBrlAmount:
    def test_standard_format(self):
        assert parse_brl_amount("R$ 1.299,90") == 1299.90

    def test_no_thousands_separator(self):
        assert parse_brl_amount("R$ 99,90") == 99.90

    def test_whole_number(self):
        assert parse_brl_amount("R$ 1.500,00") == 1500.0

    def test_with_space(self):
        assert parse_brl_amount("R$  899,00") == 899.0

    def test_none_input(self):
        assert parse_brl_amount(None) is None

    def test_empty_string(self):
        assert parse_brl_amount("") is None

    def test_no_currency_symbol(self):
        assert parse_brl_amount("1.299,90") is None


class TestParseRating:
    def test_comma_decimal(self):
        assert parse_rating("4,5 de 5 estrelas") == 4.5

    def test_whole_number(self):
        assert parse_rating("5 de 5 estrelas") == 5.0

    def test_none_input(self):
        assert parse_rating(None) is None


class TestParseReviewCount:
    def test_with_dot_separator(self):
        assert parse_review_count("1.234 avaliações") == 1234

    def test_small_number(self):
        assert parse_review_count("42 avaliações") == 42

    def test_none_input(self):
        assert parse_review_count(None) is None


class TestAmazonSearchHTMLParser:
    def test_parses_product_card(self):
        html = """
        <div data-component-type="s-search-result" data-asin="B0TEST123">
            <h2><a href="/dp/B0TEST123"><span>Mouse Gamer Logitech</span></a></h2>
            <img class="s-image" src="https://example.com/image.jpg" />
            <span class="a-price"><span class="a-offscreen">R$ 149,90</span></span>
            <span class="a-price a-text-price"><span class="a-offscreen">R$ 199,90</span></span>
        </div>
        """
        parser = AmazonSearchHTMLParser(max_results=5)
        parser.feed(html)

        assert len(parser.products) == 1
        product = parser.products[0]
        assert product["asin"] == "B0TEST123"
        assert product["title"] == "Mouse Gamer Logitech"
        assert product["url"] == "https://www.amazon.com.br/dp/B0TEST123"
        assert product["image_url"] == "https://example.com/image.jpg"
        assert product["price_text"] == "R$ 149,90"
        assert product["list_price_text"] == "R$ 199,90"

    def test_skips_card_without_title(self):
        html = """
        <div data-component-type="s-search-result" data-asin="B0TEST123">
            <span class="a-price"><span class="a-offscreen">R$ 99,90</span></span>
        </div>
        """
        parser = AmazonSearchHTMLParser(max_results=5)
        parser.feed(html)

        assert len(parser.products) == 0

    def test_respects_max_results(self):
        html = """
        <div data-component-type="s-search-result" data-asin="B0TEST001">
            <h2><a href="/dp/B0TEST001"><span>Produto 1</span></a></h2>
            <span class="a-price"><span class="a-offscreen">R$ 100,00</span></span>
        </div>
        <div data-component-type="s-search-result" data-asin="B0TEST002">
            <h2><a href="/dp/B0TEST002"><span>Produto 2</span></a></h2>
            <span class="a-price"><span class="a-offscreen">R$ 200,00</span></span>
        </div>
        """
        parser = AmazonSearchHTMLParser(max_results=1)
        parser.feed(html)

        assert len(parser.products) == 1

    def test_detects_sponsored(self):
        html = """
        <div data-component-type="s-search-result" data-asin="B0TEST123">
            <span>Patrocinado</span>
            <h2><a href="/dp/B0TEST123"><span>Produto Patrocinado</span></a></h2>
            <span class="a-price"><span class="a-offscreen">R$ 50,00</span></span>
        </div>
        """
        parser = AmazonSearchHTMLParser(max_results=5)
        parser.feed(html)

        assert len(parser.products) == 1
        assert parser.products[0]["is_sponsored"] is True


class TestBuildAffiliateUrl:
    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_builds_affiliate_url_from_asin(self):
        url = build_affiliate_url("B07GTTRBLV", None)
        assert url == "https://www.amazon.com.br/dp/B07GTTRBLV?tag=brunoentende-20"

    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_builds_affiliate_url_from_raw_url_with_asin(self):
        url = build_affiliate_url(None, "https://www.amazon.com.br/Some-Product/dp/B07GTTRBLV/ref=cm_sw_r_api?ie=UTF8")
        assert url == "https://www.amazon.com.br/dp/B07GTTRBLV?tag=brunoentende-20"

    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_prefers_asin_over_raw_url(self):
        url = build_affiliate_url("B09XXXXXXX", "https://www.amazon.com.br/dp/B07GTTRBLV")
        assert url == "https://www.amazon.com.br/dp/B09XXXXXXX?tag=brunoentende-20"

    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_falls_back_to_raw_url_when_no_asin(self):
        url = build_affiliate_url(None, "https://www.amazon.com.br/some-path")
        assert url == "https://www.amazon.com.br/some-path"

    def test_returns_none_when_no_asin_or_url(self):
        url = build_affiliate_url(None, None)
        assert url is None

    @patch("price_alert_skill.fetch_amazon_br.AMAZON_AFFILIATE_TAG", "")
    def test_returns_raw_url_when_tag_empty(self):
        url = build_affiliate_url(None, "https://www.amazon.com.br/dp/B07GTTRBLV?old=params")
        assert url == "https://www.amazon.com.br/dp/B07GTTRBLV?old=params"

    @patch("price_alert_skill.fetch_amazon_br.AMAZON_AFFILIATE_TAG", "")
    def test_returns_none_when_tag_empty_and_no_url(self):
        url = build_affiliate_url("B07GTTRBLV", None)
        assert url is None


class TestNormalizeProductsWithAffiliate:
    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_affiliate_url_applied_in_normalize(self):
        raw = [
            {
                "position": 1,
                "asin": "B07GTTRBLV",
                "title": "Mouse Gamer Redragon",
                "url": "https://www.amazon.com.br/Mouse-Gamer-Redragon/dp/B07GTTRBLV/ref=cm_sw_r_api",
                "image_url": None,
                "price_text": "R$ 149,90",
                "list_price_text": None,
                "rating_text": None,
                "review_count_text": None,
                "is_sponsored": False,
                "availability": "unknown",
            }
        ]
        products = normalize_products(raw)
        assert len(products) == 1
        assert products[0]["url"] == "https://www.amazon.com.br/dp/B07GTTRBLV?tag=brunoentende-20"

    @patch("fetch_amazon_br.AMAZON_AFFILIATE_TAG", "brunoentende-20")
    def test_affiliate_url_when_no_asin_but_url_has_dp(self):
        raw = [
            {
                "position": 1,
                "asin": None,
                "title": "Produto Qualquer",
                "url": "https://www.amazon.com.br/gp/product/B09XYZ1234",
                "image_url": None,
                "price_text": "R$ 99,00",
                "list_price_text": None,
                "rating_text": None,
                "review_count_text": None,
                "is_sponsored": False,
                "availability": "unknown",
            }
        ]
        products = normalize_products(raw)
        assert products[0]["url"] == "https://www.amazon.com.br/dp/B09XYZ1234?tag=brunoentende-20"
