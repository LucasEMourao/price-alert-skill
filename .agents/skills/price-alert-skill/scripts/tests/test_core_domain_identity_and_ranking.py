"""Tests for extracted identity and ranking helpers."""

from price_alert_skill.core.domain.identity import (
    build_offer_key,
    build_product_key,
    calculate_savings_brl,
    normalize_url_for_key,
)
from price_alert_skill.core.domain.ranking import (
    deal_sort_key,
    is_better_deal,
    sort_deals_for_sending,
)


def test_normalize_url_for_key_strips_query_and_fragment():
    assert (
        normalize_url_for_key("https://example.com/p/headset/?ref=abc#section")
        == "example.com/p/headset"
    )


def test_build_product_key_uses_normalized_url():
    assert (
        build_product_key("https://example.com/p/headset?ref=abc")
        == "example.com/p/headset"
    )


def test_build_offer_key_changes_with_price():
    product_key = "example.com/p/headset"

    assert build_offer_key(product_key, 199.9) == "example.com/p/headset|199.90"
    assert build_offer_key(product_key, None) == "example.com/p/headset"


def test_calculate_savings_brl_respects_missing_or_non_discounted_prices():
    assert calculate_savings_brl(199.9, 299.9) == 100.0
    assert calculate_savings_brl(299.9, 199.9) == 0.0
    assert calculate_savings_brl(None, 299.9) == 0.0


def test_sort_deals_for_sending_prefers_savings_then_discount_then_price():
    deals = [
        {"title": "Monitor A", "savings_brl": 100.0, "discount_pct": 20.0, "current_price": 800.0},
        {"title": "Monitor B", "savings_brl": 200.0, "discount_pct": 10.0, "current_price": 900.0},
        {"title": "Monitor C", "savings_brl": 200.0, "discount_pct": 20.0, "current_price": 850.0},
    ]

    ordered = sort_deals_for_sending(deals)

    assert [deal["title"] for deal in ordered] == ["Monitor C", "Monitor B", "Monitor A"]
    assert deal_sort_key(ordered[0]) < deal_sort_key(ordered[1])


def test_is_better_deal_prefers_higher_lane_before_sort_key():
    current = {"title": "Current", "lane": "normal", "savings_brl": 500.0, "discount_pct": 50.0, "current_price": 1000.0}
    candidate = {"title": "Candidate", "lane": "priority", "savings_brl": 300.0, "discount_pct": 30.0, "current_price": 1200.0}

    assert is_better_deal(candidate, current) is True
