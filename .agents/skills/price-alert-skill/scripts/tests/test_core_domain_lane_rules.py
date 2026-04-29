"""Tests for the extracted domain lane rules."""

from core.domain.lane_rules import (
    classify_deal_lane,
    passes_quality_filters,
    qualifies_urgent,
)


def test_gpu_deal_can_become_urgent_in_domain_rules():
    deal = {
        "category": "placas_video",
        "title": "Placa de Video RTX 5070 12GB",
        "discount_pct": 40.2,
        "savings_brl": 1600.0,
        "quality_passed": True,
    }

    assert qualifies_urgent(deal) is True
    assert classify_deal_lane(deal) == "urgent"


def test_pc_gamer_quality_requires_multiple_signal_groups():
    weak = {
        "category": "pc_gamer",
        "title": "PC Gamer Basico",
    }
    strong = {
        "category": "pc_gamer",
        "title": "PC Gamer Ryzen 7 RTX 4060 16GB SSD 1TB",
    }

    assert passes_quality_filters(weak) is False
    assert passes_quality_filters(strong) is True


def test_failed_quality_short_circuits_to_discarded():
    deal = {
        "category": "processadores",
        "title": "Processador Ryzen 7",
        "discount_pct": 50.0,
        "savings_brl": 900.0,
        "quality_passed": False,
    }

    assert classify_deal_lane(deal) == "discarded"
