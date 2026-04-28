"""Tests for expiring deal pools."""

from datetime import datetime, timedelta, timezone

from deal_queue import (
    begin_scan_run,
    get_sendable_entries,
    mark_deal_failed,
    prune_expired_entries,
    remove_entry_by_offer_key,
    upsert_pool_deal,
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
        "message": "Mensagem",
    }
    base.update(overrides)
    return prepare_deal_for_selection(base)


def _empty_queue():
    return {
        "urgent_pool": [],
        "priority_pool": [],
        "normal_pool": [],
        "meta": {"last_scan_at": None, "last_sender_tick_at": None, "scan_sequence": 0},
    }


def test_upsert_pool_deal_adds_then_updates_same_offer():
    queue = _empty_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)

    assert upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence) == "added"
    assert upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence) == "updated"
    assert len(queue["normal_pool"]) == 1
    assert queue["normal_pool"][0]["seen_count"] == 2


def test_upsert_pool_deal_replaces_same_product_when_price_changes():
    queue = _empty_queue()
    first = _deal(current_price=210.0, previous_price=299.9, discount_pct=30.0)
    second = _deal(current_price=150.0, previous_price=299.9, discount_pct=50.0)
    first_scan = begin_scan_run(queue)
    second_scan = begin_scan_run(queue)

    upsert_pool_deal(queue, first, first["lane"], scan_sequence=first_scan)
    result = upsert_pool_deal(queue, second, second["lane"], scan_sequence=second_scan)

    assert result == "replaced_product"
    assert len(queue["priority_pool"]) == 1
    assert queue["priority_pool"][0]["current_price"] == 150.0


def test_prune_expired_entries_removes_stale_items_by_time():
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(hours=4)).isoformat()
    queue = _empty_queue()
    queue["urgent_pool"].append({"offer_key": "u1", "last_seen_at": stale, "last_seen_scan": 1})
    queue["priority_pool"].append({"offer_key": "p1", "last_seen_at": stale, "last_seen_scan": 1})
    queue["normal_pool"].append({"offer_key": "n1", "last_seen_at": stale, "last_seen_scan": 1})

    updated = prune_expired_entries(queue, now=now)

    assert updated["urgent_pool"] == []
    assert updated["priority_pool"] == []
    assert updated["normal_pool"] == []


def test_mark_deal_failed_applies_retry_backoff():
    queue = _empty_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence)

    assert mark_deal_failed(queue, deal["offer_key"]) is True
    entry = queue["normal_pool"][0]
    assert entry["retry_count"] == 1
    assert entry["send_after_at"] is not None


def test_remove_entry_by_offer_key_deletes_sent_deal():
    queue = _empty_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence)

    assert remove_entry_by_offer_key(queue, deal["offer_key"]) is True
    assert queue["normal_pool"] == []


def test_get_sendable_entries_skips_backoff_items():
    queue = _empty_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence)
    mark_deal_failed(queue, deal["offer_key"])

    assert get_sendable_entries(queue, "normal") == []
