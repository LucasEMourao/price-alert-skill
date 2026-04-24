"""Tests for cadence selection rules."""

from deal_selection import (
    build_offer_key,
    build_product_key,
    get_query_category,
    prepare_deal_for_selection,
    qualifies_normal,
    round_robin_select,
)


def _base_deal(**overrides):
    deal = {
        "title": "Headset Gamer HyperX Cloud",
        "url": "https://example.com/p/headset?ref=abc",
        "product_url": "https://example.com/p/headset?ref=abc",
        "marketplace": "amazon_br",
        "current_price": 199.9,
        "previous_price": 299.9,
        "discount_pct": 33.3,
        "query": "headset gamer",
        "source_query": "headset gamer",
    }
    deal.update(overrides)
    return deal


def test_get_query_category_maps_headset_to_audio():
    assert get_query_category("headset gamer") == "audio_comunicacao"


def test_prepare_deal_for_selection_builds_keys_and_flags():
    deal = prepare_deal_for_selection(_base_deal())

    assert deal["category"] == "audio_comunicacao"
    assert deal["product_key"] == build_product_key("https://example.com/p/headset?ref=abc")
    assert deal["offer_key"] == build_offer_key(deal["product_key"], 199.9)
    assert deal["savings_brl"] == 100.0
    assert deal["is_super_promo"] is True


def test_pc_gamer_requires_two_signal_groups():
    weak = prepare_deal_for_selection(
        _base_deal(
            title="PC Gamer Basico",
            query="pc gamer",
            source_query="pc gamer",
            current_price=2999.0,
            previous_price=3599.0,
            discount_pct=16.7,
        )
    )
    strong = prepare_deal_for_selection(
        _base_deal(
            title="PC Gamer Ryzen 7 RTX 4060 16GB SSD 1TB",
            query="pc gamer",
            source_query="pc gamer",
            current_price=4999.0,
            previous_price=5999.0,
            discount_pct=16.7,
        )
    )

    assert weak["quality_passed"] is False
    assert strong["quality_passed"] is True


def test_qualifies_normal_checks_discount_and_savings():
    deal = prepare_deal_for_selection(
        _base_deal(
            current_price=260.0,
            previous_price=299.0,
            discount_pct=13.0,
        )
    )

    assert qualifies_normal(deal) is False


def test_round_robin_select_preserves_variety():
    peripherals = [
        prepare_deal_for_selection(
            _base_deal(
                title=f"Mouse Gamer {index}",
                url=f"https://example.com/mouse/{index}",
                product_url=f"https://example.com/mouse/{index}",
                query="mouse gamer",
                source_query="mouse gamer",
                current_price=100.0 + index,
                previous_price=150.0 + index,
                discount_pct=30.0,
            )
        )
        for index in range(3)
    ]
    monitors = [
        prepare_deal_for_selection(
            _base_deal(
                title=f"Monitor Gamer {index}",
                url=f"https://example.com/monitor/{index}",
                product_url=f"https://example.com/monitor/{index}",
                query="monitor gamer",
                source_query="monitor gamer",
                current_price=800.0 + index,
                previous_price=1000.0 + index,
                discount_pct=20.0,
            )
        )
        for index in range(2)
    ]

    selected = round_robin_select(
        {
            "perifericos": peripherals,
            "monitores": monitors,
        }
    )

    assert [deal["category"] for deal in selected[:2]] == ["perifericos", "monitores"]
    assert len([deal for deal in selected if deal["category"] == "perifericos"]) == 2
    assert len([deal for deal in selected if deal["category"] == "monitores"]) == 2
