from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "shopee"
FIXTURE_NAMES = (
    "product_offer_page_1.json",
    "product_offer_page_2.json",
    "product_offer_page_final.json",
    "product_offer_empty.json",
    "product_offer_graphql_error_http_200.json",
    "product_offer_price_discrepancy.json",
    "product_offer_rating_zero.json",
    "product_offer_empty_shop_type.json",
)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def product_connection(name: str) -> dict:
    payload = load_fixture(name)
    return payload["data"]["productOfferV2"]


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_shopee_fixtures_are_valid_redacted_response_bodies(fixture_name: str):
    fixture_path = FIXTURE_DIR / fixture_name
    payload = load_fixture(fixture_name)

    assert fixture_path.is_file()
    assert isinstance(payload, dict)
    assert set(payload) <= {"data", "errors"}

    serialized = fixture_path.read_text(encoding="utf-8")
    assert "Authorization" not in serialized
    assert "Bearer " not in serialized
    assert "Signature" not in serialized
    assert "AppSecret" not in serialized
    assert "SHOPEE_APP_SECRET" not in serialized


def test_successful_page_fixtures_freeze_page_based_product_offer_pagination():
    expected_pages = {
        "product_offer_page_1.json": (1, True, 2),
        "product_offer_page_2.json": (2, True, 2),
        "product_offer_page_final.json": (3, False, 1),
    }

    for fixture_name, expected in expected_pages.items():
        connection = product_connection(fixture_name)
        page_info = connection["pageInfo"]

        assert (
            page_info["page"],
            page_info["hasNextPage"],
            len(connection["nodes"]),
        ) == expected
        assert page_info["scrollId"] is None


def test_product_offer_fixture_preserves_mapping_contract_without_old_price_fields():
    node = product_connection("product_offer_page_1.json")["nodes"][0]

    assert node["productLink"] != node["offerLink"]
    assert node["priceMin"] == node["price"]
    assert node["priceDiscountRate"] == 20
    assert "previousPrice" not in node
    assert "savings" not in node
    assert "savingsBrl" not in node


def test_price_minimum_is_primary_and_price_is_the_documented_fallback():
    nodes = product_connection("product_offer_price_discrepancy.json")["nodes"]
    discrepancy_node, fallback_node = nodes

    assert discrepancy_node["priceMin"] == "199.90"
    assert fallback_node["price"] == "59.90"
    assert "priceMin" not in fallback_node


def test_empty_product_offer_fixture_is_a_valid_final_page():
    connection = product_connection("product_offer_empty.json")

    assert connection["nodes"] == []
    assert connection["pageInfo"]["hasNextPage"] is False


def test_graphql_error_fixture_represents_an_http_200_error_body():
    response_body = load_fixture("product_offer_graphql_error_http_200.json")
    http_status = 200

    assert http_status == 200
    assert response_body["data"] is None
    assert response_body["errors"][0]["extensions"]["code"] == 10035
    assert "error [10035]" in response_body["errors"][0]["message"]


def test_price_discrepancy_fixture_keeps_price_candidates_and_discount_separate():
    node = product_connection("product_offer_price_discrepancy.json")["nodes"][0]

    assert node["price"] == "219.90"
    assert node["priceMin"] == "199.90"
    assert node["price"] != node["priceMin"]
    assert node["priceMax"] == "299.90"
    assert node["priceDiscountRate"] == 33
    assert "previousPrice" not in node


def test_rating_zero_fixture_preserves_unavailable_rating_marker():
    node = product_connection("product_offer_rating_zero.json")["nodes"][0]

    assert node["ratingStar"] == "0"


def test_empty_shop_type_fixture_preserves_unknown_shop_type():
    node = product_connection("product_offer_empty_shop_type.json")["nodes"][0]

    assert node["shopType"] == []


def test_product_fixtures_do_not_expand_initial_scope_to_feed_ingestion():
    for fixture_name in FIXTURE_NAMES:
        serialized = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
        assert "listItemFeeds" not in serialized
        assert "getItemFeedData" not in serialized
