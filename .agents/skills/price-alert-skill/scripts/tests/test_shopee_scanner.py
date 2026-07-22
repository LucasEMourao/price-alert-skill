from __future__ import annotations

import copy
import json
from pathlib import Path

from price_alert_skill.core.adapters.shopee_scanner import (
    PRODUCT_OFFER_V2_QUERY,
    ShopeeMarketplaceScanner,
    build_product_offer_query,
    map_query_to_keyword,
    normalize_product_node,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "shopee"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class SequenceClient:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def execute(self, payload: dict) -> dict:
        self.calls.append(payload)
        return self.responses.pop(0)


def connection(name: str) -> dict:
    return load_fixture(name)["data"]["productOfferV2"]


def response_for_connection(value: dict) -> dict:
    return {"data": {"productOfferV2": value}}


def test_query_builder_maps_project_query_to_keyword_and_page_variables():
    payload = build_product_offer_query(page=2, keyword="  monitor   gamer ", limit=20)

    assert payload["operationName"] == "ProductOfferV2"
    assert payload["query"] == PRODUCT_OFFER_V2_QUERY
    assert payload["variables"] == {"page": 2, "limit": 20, "keyword": "monitor gamer"}
    assert map_query_to_keyword("placa de video rtx") == "placa de video rtx"


def test_scanner_fetches_first_second_and_final_pages():
    client = SequenceClient(
        [
            load_fixture("product_offer_page_1.json"),
            load_fixture("product_offer_page_2.json"),
            load_fixture("product_offer_page_final.json"),
        ]
    )

    result = ShopeeMarketplaceScanner(client=client, clock=lambda: 1_800_000_000).run(
        query="monitor gamer",
        max_results=20,
    )

    assert len(result["products"]) == 5
    assert [call["variables"]["page"] for call in client.calls] == [1, 2, 3]
    assert all(call["variables"]["keyword"] == "monitor gamer" for call in client.calls)
    assert result["pages"][-1]["has_next_page"] is False
    assert result["truncated"] is False

    product = result["products"][0]
    assert product["product_url"] != product["url"]
    assert product["product_url"] == product["product_link"]
    assert product["url"] == product["offer_link"]
    assert product["current_price"] == product["price"] == 119.90
    assert product["previous_price"] is None
    assert product["savings_brl"] is None
    assert product["discount_source"] == "shopee_price_discount_rate"
    assert product["raw_metadata"]["commissionRate"] == "0.1200"


def test_final_page_stops_without_requesting_a_fourth_page():
    client = SequenceClient([load_fixture("product_offer_page_final.json")])

    result = ShopeeMarketplaceScanner(client=client, clock=lambda: 1_800_000_000).run(
        query="cabo usb",
        max_results=10,
    )

    assert len(result["products"]) == 1
    assert len(client.calls) == 1
    assert result["errors"] == []


def test_page_safety_limit_stops_a_continuing_provider():
    client = SequenceClient(
        [
            load_fixture("product_offer_page_1.json"),
            load_fixture("product_offer_page_2.json"),
        ]
    )

    result = ShopeeMarketplaceScanner(
        client=client,
        max_pages=2,
        clock=lambda: 1_800_000_000,
    ).run(query="monitor gamer", max_results=20)

    assert len(client.calls) == 2
    assert len(result["products"]) == 4
    assert result["truncated"] is True
    assert any(error["code"] == "page_safety_limit" for error in result["errors"])


def test_malformed_nodes_are_skipped_without_aborting_the_page():
    page = load_fixture("product_offer_page_final.json")
    page["data"]["productOfferV2"]["nodes"] = [
        None,
        "not an object",
        {},
        page["data"]["productOfferV2"]["nodes"][0],
    ]
    client = SequenceClient([page])

    result = ShopeeMarketplaceScanner(client=client, clock=lambda: 1_800_000_000).run(
        query="cabo usb",
        max_results=10,
    )

    assert len(result["products"]) == 1
    assert sum(error["kind"] == "normalization" for error in result["errors"]) == 3


def test_missing_optional_fields_are_safe_and_keep_unknown_markers():
    page = load_fixture("product_offer_page_final.json")
    node = page["data"]["productOfferV2"]["nodes"][0]
    for field in ("imageUrl", "ratingStar", "shopType", "productCatIds"):
        node.pop(field)

    result = ShopeeMarketplaceScanner(
        client=SequenceClient([page]),
        clock=lambda: 1_800_000_000,
    ).run(query="cabo usb", max_results=10)
    product = result["products"][0]

    assert product["image_url"] is None
    assert product["rating"] is None
    assert product["shop_type"] == []
    assert product["product_cat_ids"] == []


def test_invalid_price_min_falls_back_to_price_but_invalid_required_values_skip():
    page = load_fixture("product_offer_page_final.json")
    node = page["data"]["productOfferV2"]["nodes"][0]
    node["priceMin"] = "not-a-number"
    result = ShopeeMarketplaceScanner(
        client=SequenceClient([page]),
        clock=lambda: 1_800_000_000,
    ).run(query="cabo usb", max_results=10)
    assert result["products"][0]["current_price"] == 79.90

    invalid_discount = load_fixture("product_offer_page_final.json")
    invalid_discount["data"]["productOfferV2"]["nodes"][0]["priceDiscountRate"] = "NaN"
    invalid_result = ShopeeMarketplaceScanner(
        client=SequenceClient([invalid_discount]),
        clock=lambda: 1_800_000_000,
    ).run(query="cabo usb", max_results=10)
    assert invalid_result["products"] == []
    assert invalid_result["errors"][0]["field"] == "priceDiscountRate"


def test_price_discrepancy_is_diagnostic_and_price_min_remains_primary():
    client = SequenceClient([load_fixture("product_offer_price_discrepancy.json")])

    result = ShopeeMarketplaceScanner(client=client, clock=lambda: 1_800_000_000).run(
        query="monitor gamer",
        max_results=10,
    )

    product = result["products"][0]
    assert product["current_price"] == 199.90
    assert product["price_max"] == 299.90
    assert product["previous_price"] is None
    assert product["price_discrepancy"] == {
        "type": "price_discrepancy",
        "price_min": 199.90,
        "price": 219.90,
    }
    assert any(item["type"] == "price_discrepancy" for item in result["diagnostics"])


def test_duplicate_item_ids_are_returned_once_across_pages():
    first = load_fixture("product_offer_page_final.json")
    duplicate = copy.deepcopy(first)
    duplicate_node = duplicate["data"]["productOfferV2"]["nodes"][0]
    duplicate_node["productName"] = "Same item with another title"
    duplicate["data"]["productOfferV2"]["pageInfo"]["page"] = 2
    duplicate["data"]["productOfferV2"]["pageInfo"]["hasNextPage"] = False
    client = SequenceClient([first, duplicate])

    # First page is final, so a second response must only be used by a
    # page-continued variant of the fixture.
    first["data"]["productOfferV2"]["pageInfo"]["hasNextPage"] = True
    result = ShopeeMarketplaceScanner(client=client, clock=lambda: 1_800_000_000).run(
        query="cabo usb",
        max_results=10,
    )

    assert len(result["products"]) == 1
    assert any(item["type"] == "duplicate_product" for item in result["diagnostics"])


def test_period_filter_skips_future_and_expired_offers():
    page = load_fixture("product_offer_page_final.json")
    base = page["data"]["productOfferV2"]["nodes"][0]
    future = copy.deepcopy(base)
    future["itemId"] = 1
    future["periodStartTime"] = 2_000_000_001
    expired = copy.deepcopy(base)
    expired["itemId"] = 2
    expired["periodEndTime"] = 1_000_000_000
    active = copy.deepcopy(base)
    active["itemId"] = 3
    active["periodStartTime"] = 1_000_000_000
    active["periodEndTime"] = 2_000_000_000
    missing_period = copy.deepcopy(base)
    missing_period["itemId"] = 4
    missing_period.pop("periodStartTime")
    missing_period.pop("periodEndTime")
    page["data"]["productOfferV2"]["nodes"] = [future, expired, active, missing_period]

    result = ShopeeMarketplaceScanner(
        client=SequenceClient([page]),
        clock=lambda: 1_800_000_000,
    ).run(query="cabo usb", max_results=10)

    assert [product["item_id"] for product in result["products"]] == [3, 4]


def test_http_200_graphql_errors_become_structured_provider_errors():
    error_body = load_fixture("product_offer_graphql_error_http_200.json")
    client = SequenceClient([error_body])

    result = ShopeeMarketplaceScanner(client=client).run(
        query="monitor gamer",
        max_results=10,
    )

    assert result["products"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0]["code"] == 10035
    assert result["errors"][0]["kind"] == "access"
    assert result["errors"][0]["status_code"] == 200


def test_normalize_product_node_handles_rating_zero_and_does_not_use_price_max_as_old_price():
    node = load_fixture("product_offer_rating_zero.json")["data"]["productOfferV2"]["nodes"][0]

    product = normalize_product_node(node, now=1_800_000_000)

    assert product is not None
    assert product["rating"] is None
    assert product["price_max"] == 89.90
    assert product["previous_price"] is None
    assert product["raw"]["ratingStar"] == "0"
