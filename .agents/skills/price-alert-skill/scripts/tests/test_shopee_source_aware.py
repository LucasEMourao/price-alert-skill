from datetime import datetime, timedelta, timezone

from price_alert_skill.core.application.scan_use_case import (
    deduplicate_run_deals,
    extract_deals_from_products,
)
from price_alert_skill.core.domain.dedup_policy import can_send_again
from price_alert_skill.core.domain.lane_rules import (
    SHOPEE_LANE_THRESHOLDS,
    classify_deal_lane,
)
from price_alert_skill.core.domain.ranking import sort_deals_for_sending
from price_alert_skill.deal_selection import prepare_deal_for_selection
from price_alert_skill.utils import calculate_discount, format_deal_message


SHOPEE_SOURCE = "shopee_price_discount_rate"


def _shopee_product(**overrides):
    product = {
        "marketplace": "shopee_br",
        "title": "SSD NVMe 1TB",
        "url": "https://shopee.ee/affiliate-offer",
        "product_url": "https://shopee.com.br/produto/1",
        "current_price": 100.0,
        "price_discount_rate": 30,
        "discount_pct": 2,
        "discount_source": SHOPEE_SOURCE,
        "previous_price": 999.0,
        "savings_brl": 899.0,
        "query": "ssd nvme 1tb",
    }
    product.update(overrides)
    return product


def _shopee_deal(**overrides):
    product = _shopee_product(**overrides)
    deal = extract_deals_from_products(
        [product],
        "shopee_br",
        "ssd nvme 1tb",
        1.0,
        calculate_discount_fn=calculate_discount,
    )
    assert len(deal) == 1
    return prepare_deal_for_selection(deal[0])


def test_shopee_qualification_uses_price_discount_rate_only():
    deals = extract_deals_from_products(
        [_shopee_product(price_discount_rate=20, discount_pct=1)],
        "shopee_br",
        "ssd nvme 1tb",
        10.0,
        calculate_discount_fn=calculate_discount,
    )

    assert len(deals) == 1
    assert deals[0]["discount_pct"] == 20.0
    assert deals[0]["previous_price"] is None
    assert deals[0]["savings_brl"] is None


def test_shopee_zero_or_missing_source_discount_is_not_qualified():
    zero_discount = extract_deals_from_products(
        [_shopee_product(price_discount_rate=0, discount_pct=80)],
        "shopee_br",
        "ssd nvme 1tb",
        0.0,
        calculate_discount_fn=calculate_discount,
    )
    missing_source = extract_deals_from_products(
        [_shopee_product(discount_source=None, price_discount_source=None)],
        "shopee_br",
        "ssd nvme 1tb",
        0.0,
        calculate_discount_fn=calculate_discount,
    )

    assert zero_discount == []
    assert missing_source == []


def test_shopee_lane_thresholds_are_explicit_and_ignore_unknown_savings():
    assert SHOPEE_LANE_THRESHOLDS == {
        "normal": 10.0,
        "priority": 25.0,
        "urgent": 40.0,
    }

    for discount, expected_lane in (
        (9.9, "discarded"),
        (10.0, "normal"),
        (24.9, "normal"),
        (25.0, "priority"),
        (39.9, "priority"),
        (40.0, "urgent"),
    ):
        deal = _shopee_deal(price_discount_rate=discount, savings_brl=99999.0)
        assert deal["savings_brl"] is None
        assert classify_deal_lane(deal) == expected_lane


def test_shopee_prepare_sanitizes_previous_price_and_savings():
    deal = _shopee_deal(previous_price=999.0, savings_brl=899.0)

    assert deal["previous_price"] is None
    assert deal["previous_price_text"] is None
    assert deal["savings_brl"] is None
    assert deal["discount_pct"] == 30.0
    assert deal["discount_source"] == SHOPEE_SOURCE


def test_shopee_message_shows_percentage_and_current_price_without_antes():
    message = format_deal_message(_shopee_deal(price_discount_rate=30))

    assert "🔥 30% OFF" in message
    assert "🎯 Hoje: R$ 100,00" in message
    assert "Antes:" not in message
    assert "R$ 999,00" not in message
    assert "https://shopee.ee/affiliate-offer" in message


def test_shopee_ranking_uses_percentage_when_savings_are_unknown():
    lower = _shopee_deal(price_discount_rate=20, title="SSD A")
    higher = _shopee_deal(price_discount_rate=30, title="SSD B")

    ordered = sort_deals_for_sending([lower, higher])

    assert [deal["title"] for deal in ordered] == ["SSD B", "SSD A"]


def test_shopee_dedup_uses_canonical_product_and_current_price():
    same_offer_a = _shopee_deal(url="https://shopee.ee/offer-a")
    same_offer_b = _shopee_deal(url="https://shopee.ee/offer-b")
    changed_price = _shopee_deal(
        url="https://shopee.ee/offer-c",
        current_price=90.0,
    )

    unique = deduplicate_run_deals([same_offer_a, same_offer_b, changed_price])

    assert len(unique) == 2
    assert same_offer_a["product_key"] == same_offer_b["product_key"]
    assert same_offer_a["offer_key"] != changed_price["offer_key"]
    assert same_offer_a["product_key"] == changed_price["product_key"]
    assert same_offer_a["dedup_key"] != changed_price["dedup_key"]


def test_shopee_cooldown_uses_discount_improvement_not_unknown_savings():
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    sent_data = {
        "sent": {
            "shopee.com.br/produto/1|100.00": {
                "product_key": "shopee.com.br/produto/1",
                "sent_at": (now - timedelta(hours=2)).isoformat(),
                "discount_pct": 20.0,
                "savings_brl": None,
                "lane": "normal",
                "is_super_promo": False,
            }
        },
        "last_cleaned": None,
    }

    same_offer = _shopee_deal(price_discount_rate=20)
    improved = _shopee_deal(price_discount_rate=25, current_price=90.0)

    assert can_send_again(same_offer, sent_data, now=now, cadence_config={
        "same_offer_cooldown_hours": 24,
        "urgent_offer_cooldown_hours": 6,
        "min_discount_improvement_points": 5.0,
        "min_savings_improvement_brl": 50.0,
    }) is False
    assert can_send_again(improved, sent_data, now=now, cadence_config={
        "same_offer_cooldown_hours": 24,
        "urgent_offer_cooldown_hours": 6,
        "min_discount_improvement_points": 5.0,
        "min_savings_improvement_brl": 50.0,
    }) is True


def test_amazon_and_mercado_livre_price_pair_behavior_is_unchanged():
    amazon = extract_deals_from_products(
        [{
            "title": "Mouse Amazon",
            "url": "https://amazon.com.br/dp/1",
            "price": 75.0,
            "list_price": 100.0,
            "list_price_source": "amazon_list_price",
        }],
        "amazon_br",
        "mouse gamer",
        10.0,
        calculate_discount_fn=calculate_discount,
    )
    mercado_livre = extract_deals_from_products(
        [{
            "title": "Mouse Mercado Livre",
            "url": "https://mercadolivre.com.br/item/1",
            "price": 80.0,
            "list_price": 100.0,
        }],
        "mercadolivre_br",
        "mouse gamer",
        10.0,
        calculate_discount_fn=calculate_discount,
    )

    amazon_prepared = prepare_deal_for_selection(amazon[0])
    mercado_livre_prepared = prepare_deal_for_selection(mercado_livre[0])

    assert amazon_prepared["previous_price"] == 100.0
    assert amazon_prepared["savings_brl"] == 25.0
    assert mercado_livre_prepared["previous_price"] == 100.0
    assert mercado_livre_prepared["discount_pct"] == 20.0
    assert "💰 Antes: ~R$ 100,00~" in format_deal_message(amazon_prepared)
    assert "💰 Antes: ~R$ 100,00~" in format_deal_message(mercado_livre_prepared)
