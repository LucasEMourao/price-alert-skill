from price_alert_skill.core.application.scan_use_case import extract_deals_from_products
from price_alert_skill.fetch_amazon_br import AmazonSearchHTMLParser, normalize_products
from price_alert_skill.utils import calculate_discount


def parse_products(card_html: str) -> list[dict]:
    parser = AmazonSearchHTMLParser(max_results=10)
    parser.feed(card_html)
    return normalize_products(parser.products)


def test_amazon_parser_uses_struck_price_not_unit_price_as_list_price() -> None:
    products = parse_products(
        """
        <div data-component-type="s-search-result" data-asin="B0789T6ML8">
          <a href="/dp/B0789T6ML8">
            Nupill Creme Area Dos Olhos Q10 30G Azul
          </a>
          <span class="a-price">
            <span class="a-offscreen">R$ 33,29</span>
          </span>
          <span>kg por </span>
          <span class="a-price a-text-price" data-a-size="b" data-a-color="secondary">
            <span class="a-offscreen">R$ 1.109,67</span>
          </span>
          <span>/ kg</span>
          <span>De: </span>
          <span class="a-price a-text-price" data-a-strike="true" data-a-color="secondary">
            <span class="a-offscreen">R$ 40,70</span>
          </span>
        </div>
        """
    )

    assert len(products) == 1
    product = products[0]
    assert product["price"] == 33.29
    assert product["list_price"] == 40.70
    assert product["list_price_source"] == "amazon_list_price"
    assert {"text": "R$ 1.109,67", "role": "unit"} in product["price_evidence"]

    deals = extract_deals_from_products(
        products,
        "amazon_br",
        "creme olhos",
        10.0,
        calculate_discount_fn=calculate_discount,
    )

    assert len(deals) == 1
    assert deals[0]["previous_price"] == 40.70
    assert deals[0]["discount_pct"] == 18.2


def test_amazon_unit_price_alone_does_not_create_discount_deal() -> None:
    products = parse_products(
        """
        <div data-component-type="s-search-result" data-asin="B0789T6ML8">
          <a href="/dp/B0789T6ML8">
            Nupill Creme Area Dos Olhos Q10 30G Azul
          </a>
          <span class="a-price">
            <span class="a-offscreen">R$ 33,29</span>
          </span>
          <span>kg por </span>
          <span class="a-price a-text-price" data-a-size="b" data-a-color="secondary">
            <span class="a-offscreen">R$ 1.109,67</span>
          </span>
          <span>/ kg</span>
        </div>
        """
    )

    assert len(products) == 1
    product = products[0]
    assert product["price"] == 33.29
    assert product["list_price"] is None
    assert {"text": "R$ 1.109,67", "role": "unit"} in product["price_evidence"]

    deals = extract_deals_from_products(
        products,
        "amazon_br",
        "creme olhos",
        10.0,
        calculate_discount_fn=calculate_discount,
    )

    assert deals == []


def test_amazon_deal_filter_requires_verified_list_price_source() -> None:
    products = [
        {
            "title": "Produto com preco unitario confundido",
            "url": "https://www.amazon.com.br/dp/B0789T6ML8",
            "price": 33.29,
            "price_text": "R$ 33,29",
            "list_price": 1109.67,
            "list_price_text": "R$ 1.109,67",
            "price_evidence": [{"text": "R$ 1.109,67", "role": "unit"}],
        }
    ]

    deals = extract_deals_from_products(
        products,
        "amazon_br",
        "creme olhos",
        10.0,
        calculate_discount_fn=calculate_discount,
    )

    assert deals == []
