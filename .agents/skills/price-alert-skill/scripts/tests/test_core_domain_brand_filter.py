"""Tests for beauty brand allowlist matching."""

from price_alert_skill.core.domain.brand_filter import (
    match_allowed_beauty_brand,
    normalize_brand_text,
    parse_configured_brand_names,
    resolve_brand_definitions,
)


def test_normalize_brand_text_removes_accents_and_punctuation():
    assert normalize_brand_text("L'Oréal Paris - Sérum!") == "loreal paris serum"


def test_loose_matching_accepts_marketplace_title_variants():
    assert match_allowed_beauty_brand("Kit Boticário Lily com desconto").brand == "O Boticario"
    assert match_allowed_beauty_brand("Base Loreal Paris True Match").brand == "L'Oreal Paris"
    assert match_allowed_beauty_brand("Protetor La Roche Posay Anthelios").brand == "La Roche"
    assert match_allowed_beauty_brand("Delineador Quem Disse, Berenice?").brand == "Quem Disse Berenice"


def test_word_boundaries_avoid_short_brand_false_positives():
    assert match_allowed_beauty_brand("Maquiagem compacta profissional").brand is None
    assert match_allowed_beauty_brand("Batom MAC Ruby Woo").brand == "MAC Cosmetics"


def test_configured_brand_names_select_default_alias_groups():
    definitions = resolve_brand_definitions(("loreal", "boticario"))

    assert [definition.canonical for definition in definitions] == [
        "L'Oreal Paris",
        "O Boticario",
    ]
    assert match_allowed_beauty_brand(
        "Base Loreal Paris",
        allowed_brand_names=("loreal",),
    ).brand == "L'Oreal Paris"
    assert not match_allowed_beauty_brand(
        "Perfume Natura",
        allowed_brand_names=("loreal",),
    ).passed


def test_parse_configured_brand_names_accepts_comma_or_semicolon_lists():
    assert parse_configured_brand_names("loreal, boticario") == ("loreal", "boticario")
    assert parse_configured_brand_names("Quem Disse, Berenice?; Natura") == (
        "Quem Disse, Berenice?",
        "Natura",
    )
