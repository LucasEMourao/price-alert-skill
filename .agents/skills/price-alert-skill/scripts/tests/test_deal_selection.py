"""Tests for deal lane selection rules."""

from price_alert_skill.deal_selection import (
    build_offer_key,
    build_product_key,
    classify_deal_lane,
    get_queries,
    get_query_category,
    get_query_categories,
    get_query_definitions,
    get_query_profile,
    get_query_profiles,
    prepare_deal_for_selection,
    qualifies_normal,
    qualifies_priority,
    qualifies_urgent,
    sort_deals_for_sending,
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


def test_default_query_profile_preserves_tech_catalog():
    queries = get_queries()

    assert get_query_profiles() == ("tech", "beauty")
    assert queries[0] == "mouse gamer"
    assert "placa de video rtx" in queries
    assert "perfume feminino" not in queries


def test_beauty_query_profile_contains_grouped_feminine_products():
    definitions = get_query_definitions("beauty")
    queries = [definition["query"] for definition in definitions]
    categories = {definition["category"] for definition in definitions}

    assert "perfume feminino" in queries
    assert "serum vitamina c" in queries
    assert "escova secadora" in queries
    assert "batom liquido" in queries
    assert "cabine uv led unha" in queries
    assert "pente cabelo cacheado" in queries
    assert categories == {
        "beleza_acessorios",
        "beleza_cabelo_ferramentas",
        "beleza_cabelo_tratamento",
        "beleza_corpo_banho",
        "beleza_maquiagem",
        "beleza_perfumes",
        "beleza_skincare",
        "beleza_unhas",
    }


def test_beauty_query_profile_can_be_filtered_by_category():
    queries = get_queries("beauty", "beleza_perfumes")

    assert queries == [
        "perfume feminino",
        "body splash",
        "kit perfume feminino",
        "perfume importado feminino",
        "perfume arabe feminino",
        "miniatura perfume feminino",
    ]
    assert "beleza_perfumes" in get_query_categories("beauty")


def test_unknown_query_category_raises_value_error():
    try:
        get_queries("beauty", "beleza_inexistente")
    except ValueError as exc:
        assert "Available categories" in str(exc)
    else:
        raise AssertionError("Expected get_queries to reject unknown categories")


def test_get_query_category_and_profile_map_beauty_queries():
    assert get_query_category("perfume feminino") == "beleza_perfumes"
    assert get_query_category("serum acido hialuronico") == "beleza_skincare"
    assert get_query_profile("batom liquido") == "beauty"


def test_unknown_query_profile_raises_value_error():
    try:
        get_queries("unknown")
    except ValueError as exc:
        assert "Available profiles" in str(exc)
    else:
        raise AssertionError("Expected get_queries to reject unknown profiles")


def test_prepare_deal_for_selection_builds_keys_and_lane():
    deal = prepare_deal_for_selection(_base_deal())

    assert deal["category"] == "audio_comunicacao"
    assert deal["product_key"] == build_product_key("https://example.com/p/headset?ref=abc")
    assert deal["offer_key"] == build_offer_key(deal["product_key"], 199.9)
    assert deal["savings_brl"] == 100.0
    assert deal["lane"] == "normal"
    assert deal["is_super_promo"] is False


def test_gpu_can_become_urgent():
    deal = prepare_deal_for_selection(
        _base_deal(
            title="Placa de Video RTX 5070 12GB",
            url="https://example.com/gpu",
            product_url="https://example.com/gpu",
            query="placa de video rtx",
            source_query="placa de video rtx",
            current_price=2999.0,
            previous_price=4599.0,
            discount_pct=40.2,
        )
    )

    assert qualifies_urgent(deal) is True
    assert classify_deal_lane(deal) == "urgent"


def test_audio_priority_requires_stronger_threshold():
    deal = prepare_deal_for_selection(_base_deal())

    assert qualifies_normal(deal) is True
    assert qualifies_priority(deal) is False
    assert classify_deal_lane(deal) == "normal"


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
    assert weak["lane"] == "discarded"
    assert strong["quality_passed"] is True


def test_sort_deals_for_sending_prefers_higher_savings_then_discount():
    lower = prepare_deal_for_selection(
        _base_deal(
            title="Monitor A",
            url="https://example.com/a",
            product_url="https://example.com/a",
            query="monitor gamer",
            source_query="monitor gamer",
            current_price=850.0,
            previous_price=1000.0,
            discount_pct=15.0,
        )
    )
    higher = prepare_deal_for_selection(
        _base_deal(
            title="Monitor B",
            url="https://example.com/b",
            product_url="https://example.com/b",
            query="monitor gamer",
            source_query="monitor gamer",
            current_price=700.0,
            previous_price=1000.0,
            discount_pct=30.0,
        )
    )

    ordered = sort_deals_for_sending([lower, higher])
    assert [deal["title"] for deal in ordered] == ["Monitor B", "Monitor A"]
