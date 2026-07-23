from __future__ import annotations

from datetime import datetime, timezone

import price_alert_skill.config as config
from price_alert_skill import sender_worker
from price_alert_skill.core.application.scan_use_case import (
    deduplicate_run_deals,
    scan_all,
    scan_marketplace,
)
from price_alert_skill.core.domain.queue_policy import (
    begin_scan_run,
    default_queue,
    get_sendable_entries,
    upsert_pool_deal,
)
from price_alert_skill.deal_selection import prepare_deal_for_selection
from price_alert_skill.utils import calculate_discount


SHOPEE_SOURCE = "shopee_price_discount_rate"


def _shopee_product(**overrides):
    product = {
        "title": "SSD NVMe 1TB",
        "url": "https://affiliate.shopee.com.br/offer/1",
        "offer_link": "https://affiliate.shopee.com.br/offer/1",
        "product_url": "https://shopee.com.br/produto/1?utm_source=scan",
        "current_price": 100.0,
        "price_discount_rate": 30.0,
        "discount_source": SHOPEE_SOURCE,
        "image_url": "https://shopee.com.br/image.jpg",
    }
    product.update(overrides)
    return product


def _shopee_deal(**overrides):
    products = [_shopee_product(**overrides)]
    deals = scan_marketplace(
        "shopee_br",
        "ssd nvme 1tb",
        5,
        10.0,
        amazon_runner=lambda **_: {"products": []},
        mercadolivre_runner=lambda **_: {"products": []},
        shopee_runner=lambda **_: {"products": products, "pages": [{"page": 1}]},
        calculate_discount_fn=calculate_discount,
    )
    assert len(deals) == 1
    return prepare_deal_for_selection(deals[0])


def test_shopee_dispatch_uses_injected_runner_and_keeps_affiliate_url_separate():
    calls = []
    deal = scan_marketplace(
        "shopee_br",
        "ssd nvme 1tb",
        5,
        10.0,
        amazon_runner=lambda **_: {"products": []},
        mercadolivre_runner=lambda **_: {"products": []},
        shopee_runner=lambda **kwargs: calls.append(kwargs) or {
            "products": [_shopee_product()]
        },
        calculate_discount_fn=calculate_discount,
    )

    assert calls == [{"query": "ssd nvme 1tb", "max_results": 5}]
    assert deal[0]["url"] == "https://affiliate.shopee.com.br/offer/1"
    assert deal[0]["affiliate_url"] == deal[0]["url"]
    assert deal[0]["product_url"] == "https://shopee.com.br/produto/1?utm_source=scan"
    assert deal[0]["source_product_key"] == "shopee.com.br/produto/1"


def test_mixed_scan_continues_when_shopee_is_unavailable():
    calls = []

    def scan_one(marketplace, query, max_results, min_discount):
        calls.append(marketplace)
        if marketplace == "shopee_br":
            raise RuntimeError("Shopee outage")
        return [{"marketplace": marketplace, "query": query}]

    deals = scan_all(
        5,
        10.0,
        ["shopee_br", "amazon_br", "mercadolivre_br"],
        ["monitor gamer"],
        scan_marketplace_fn=scan_one,
        logger=lambda _: None,
    )

    assert calls == ["shopee_br", "amazon_br", "mercadolivre_br"]
    assert [deal["marketplace"] for deal in deals] == [
        "amazon_br",
        "mercadolivre_br",
    ]


def test_default_marketplace_configuration_is_preserved_and_shopee_is_opt_in(monkeypatch):
    monkeypatch.delenv("PRICE_ALERT_MARKETPLACES", raising=False)
    assert config.resolve_price_alert_marketplaces() == (
        "amazon_br",
        "mercadolivre_br",
    )

    monkeypatch.setenv("PRICE_ALERT_MARKETPLACES", "shopee_br, amazon_br, shopee_br")
    assert config.resolve_price_alert_marketplaces() == ("shopee_br", "amazon_br")


def test_shopee_scan_deals_are_deduplicated_by_canonical_product_and_price():
    first = {
        **_shopee_product(),
        "product_url": "https://shopee.com.br/produto/1?tracking=a",
        "url": "https://affiliate.shopee.com.br/offer/a",
    }
    second = {
        **_shopee_product(),
        "product_url": "https://shopee.com.br/produto/1?tracking=b",
        "url": "https://affiliate.shopee.com.br/offer/b",
    }
    changed_price = {**second, "current_price": 90.0}
    deals = [
        scan_marketplace(
            "shopee_br",
            "ssd nvme 1tb",
            5,
            10.0,
            amazon_runner=lambda **_: {"products": []},
            mercadolivre_runner=lambda **_: {"products": []},
            shopee_runner=lambda **_: {"products": [product]},
            calculate_discount_fn=calculate_discount,
        )[0]
        for product in (first, second, changed_price)
    ]

    unique = deduplicate_run_deals(deals)
    prepared = [prepare_deal_for_selection(deal) for deal in unique]

    assert len(unique) == 2
    assert prepared[0]["product_key"] == prepared[1]["product_key"]
    assert prepared[0]["offer_key"] != prepared[1]["offer_key"]


def test_queue_insertion_and_sender_rollback_filter_preserve_profile_brand_rules(monkeypatch):
    beauty = _shopee_deal(
        title="Natura Perfume Feminino",
        product_url="https://shopee.com.br/perfume/1",
        price_discount_rate=40.0,
    )
    beauty["product_profile"] = "beauty"
    beauty["category"] = "beleza_perfumes"
    beauty["brand_filter_passed"] = True
    beauty["allowed_brand"] = "Natura"
    beauty["lane"] = "priority"

    blocked = dict(beauty)
    blocked["title"] = "Eudora Perfume Feminino"
    blocked["product_url"] = "https://shopee.com.br/perfume/2"
    blocked["product_key"] = "shopee.com.br/perfume/2"
    blocked["offer_key"] = f"{blocked['product_key']}|100.00"
    blocked["brand_filter_passed"] = False
    blocked["allowed_brand"] = None

    queue = default_queue()
    sequence = begin_scan_run(queue, datetime.now(timezone.utc))
    upsert_pool_deal(queue, beauty, "priority", scan_sequence=sequence)
    upsert_pool_deal(queue, blocked, "priority", scan_sequence=sequence)

    assert len(queue["priority_pool"]) == 2
    assert [entry["marketplace"] for entry in get_sendable_entries(
        queue,
        "priority",
        product_profile="beauty",
        allowed_beauty_brand_names=("natura",),
        allowed_marketplaces=("shopee_br",),
    )] == ["shopee_br"]

    monkeypatch.setenv("PRICE_ALERT_SEND_MARKETPLACES", "amazon_br,mercadolivre_br")
    assert sender_worker._get_sendable_entries_for_sender(
        queue,
        "priority",
        product_profile="beauty",
    ) == []


def test_empty_sender_marketplace_allowlist_does_not_filter_existing_entries(monkeypatch):
    monkeypatch.setenv("PRICE_ALERT_SEND_MARKETPLACES", "")
    deal = _shopee_deal(price_discount_rate=40.0)
    deal["lane"] = "urgent"
    queue = default_queue()
    sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, "urgent", scan_sequence=sequence)

    selected = sender_worker._get_sendable_entries_for_sender(queue, "urgent")

    assert selected and selected[0]["marketplace"] == "shopee_br"
    assert config.resolve_price_alert_send_marketplaces() is None
