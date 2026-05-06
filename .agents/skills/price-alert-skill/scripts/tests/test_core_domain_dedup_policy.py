"""Tests for extracted dedup and resend policies."""

from datetime import datetime, timedelta, timezone

from price_alert_skill.core.domain.dedup_policy import (
    build_sent_record,
    can_send_again,
    clean_old_deals,
    normalize_sent_deals_data,
)


CADENCE_CONFIG = {
    "same_offer_cooldown_hours": 24,
    "urgent_offer_cooldown_hours": 6,
    "min_discount_improvement_points": 5.0,
    "min_savings_improvement_brl": 50.0,
}


def test_build_sent_record_marks_urgent_as_super_promo():
    record = build_sent_record(
        {
            "offer_key": "offer-1",
            "product_key": "product-1",
            "lane": "urgent",
            "title": "RTX 5070",
            "current_price": 2999.0,
        },
        sent_at="2026-04-29T10:00:00+00:00",
    )

    assert record["product_key"] == "product-1"
    assert record["lane"] == "urgent"
    assert record["is_super_promo"] is True


def test_normalize_sent_deals_data_handles_legacy_string_records():
    normalized = normalize_sent_deals_data(
        {
            "sent": {
                "offer-1": "2026-04-29T10:00:00+00:00",
            },
            "last_cleaned": None,
        }
    )

    assert normalized["sent"]["offer-1"]["product_key"] == "offer-1"
    assert normalized["sent"]["offer-1"]["lane"] == "normal"


def test_clean_old_deals_keeps_recent_and_removes_stale_records():
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    data = {
        "sent": {
            "recent": {"product_key": "p1", "sent_at": (now - timedelta(days=1)).isoformat()},
            "stale": {"product_key": "p2", "sent_at": (now - timedelta(days=10)).isoformat()},
        },
        "last_cleaned": None,
    }

    cleaned = clean_old_deals(data, now=now, max_age_days=7)

    assert "recent" in cleaned["sent"]
    assert "stale" not in cleaned["sent"]


def test_can_send_again_blocks_same_normal_offer_inside_24h():
    now = datetime.now(timezone.utc)
    sent_data = {
        "sent": {
            "offer-1": {
                "product_key": "product-1",
                "sent_at": (now - timedelta(hours=2)).isoformat(),
                "lane": "normal",
                "is_super_promo": False,
            }
        },
        "last_cleaned": None,
    }
    deal = {
        "offer_key": "offer-1",
        "product_key": "product-1",
        "lane": "normal",
        "url": "https://example.com/p1",
    }

    assert can_send_again(deal, sent_data, now=now, cadence_config=CADENCE_CONFIG) is False


def test_can_send_again_allows_same_urgent_offer_after_6h():
    now = datetime.now(timezone.utc)
    sent_data = {
        "sent": {
            "offer-1": {
                "product_key": "product-1",
                "sent_at": (now - timedelta(hours=7)).isoformat(),
                "lane": "urgent",
                "is_super_promo": True,
            }
        },
        "last_cleaned": None,
    }
    deal = {
        "offer_key": "offer-1",
        "product_key": "product-1",
        "lane": "urgent",
        "is_super_promo": True,
        "url": "https://example.com/p1",
    }

    assert can_send_again(deal, sent_data, now=now, cadence_config=CADENCE_CONFIG) is True


def test_can_send_again_allows_same_product_when_discount_improves():
    now = datetime.now(timezone.utc)
    sent_data = {
        "sent": {
            "offer-1": {
                "product_key": "product-1",
                "sent_at": now.isoformat(),
                "discount_pct": 15.0,
                "savings_brl": 70.0,
                "is_super_promo": False,
                "lane": "normal",
            }
        },
        "last_cleaned": None,
    }
    deal = {
        "offer_key": "offer-2",
        "product_key": "product-1",
        "discount_pct": 21.0,
        "savings_brl": 80.0,
        "is_super_promo": False,
        "lane": "normal",
        "url": "https://example.com/p1",
    }

    assert can_send_again(deal, sent_data, now=now, cadence_config=CADENCE_CONFIG) is True
