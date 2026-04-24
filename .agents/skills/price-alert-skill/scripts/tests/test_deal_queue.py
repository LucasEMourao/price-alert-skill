"""Tests for cadence deal queue persistence helpers."""

from datetime import datetime, timedelta, timezone

from deal_queue import (
    drop_expired_entries,
    enqueue_or_update_normal,
    enqueue_urgent_retry,
    increment_retry_count,
)
from deal_selection import prepare_deal_for_selection


def _deal(**overrides):
    base = {
        "title": "Headset Gamer HyperX",
        "url": "https://example.com/p/headset",
        "product_url": "https://example.com/p/headset",
        "marketplace": "amazon_br",
        "current_price": 199.9,
        "previous_price": 299.9,
        "discount_pct": 33.3,
        "query": "headset gamer",
        "source_query": "headset gamer",
        "image_url": "https://example.com/headset.jpg",
    }
    base.update(overrides)
    return prepare_deal_for_selection(base)


def test_enqueue_or_update_normal_adds_then_updates_same_offer():
    queue = {"normal": [], "urgent_retry": [], "meta": {}}
    deal = _deal()

    assert enqueue_or_update_normal(queue, deal) == "added"
    assert enqueue_or_update_normal(queue, deal) == "updated"
    assert len(queue["normal"]) == 1


def test_enqueue_or_update_normal_replaces_worse_same_product():
    queue = {"normal": [], "urgent_retry": [], "meta": {}}
    worse = _deal(current_price=230.0, previous_price=299.9, discount_pct=23.3)
    better = _deal(current_price=180.0, previous_price=299.9, discount_pct=40.0)

    enqueue_or_update_normal(queue, worse)
    result = enqueue_or_update_normal(queue, better)

    assert result == "replaced"
    assert queue["normal"][0]["current_price"] == 180.0


def test_enqueue_urgent_retry_updates_existing_offer():
    queue = {"normal": [], "urgent_retry": [], "meta": {}}
    deal = _deal()

    assert enqueue_urgent_retry(queue, deal) == "added"
    assert enqueue_urgent_retry(queue, deal) == "updated"
    assert len(queue["urgent_retry"]) == 1


def test_drop_expired_entries_removes_stale_normal_and_urgent():
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(hours=3)).isoformat()
    fresh = now.isoformat()
    queue = {
        "normal": [{"offer_key": "normal-stale", "last_seen_at": stale}],
        "urgent_retry": [{"offer_key": "urgent-stale", "first_seen_at": stale}],
        "meta": {},
    }

    queue["normal"].append({"offer_key": "normal-fresh", "last_seen_at": fresh})
    queue["urgent_retry"].append({"offer_key": "urgent-fresh", "first_seen_at": fresh})

    updated = drop_expired_entries(queue, now)

    assert [entry["offer_key"] for entry in updated["normal"]] == ["normal-fresh"]
    assert [entry["offer_key"] for entry in updated["urgent_retry"]] == ["urgent-fresh"]


def test_increment_retry_count_drops_exhausted_entries():
    queue = {
        "normal": [{"offer_key": "normal-1", "retry_count": 2}],
        "urgent_retry": [{"offer_key": "urgent-1", "retry_count": 3}],
        "meta": {},
    }

    updated = increment_retry_count(queue, {"normal-1", "urgent-1"})

    assert updated["normal"] == []
    assert updated["urgent_retry"] == []
