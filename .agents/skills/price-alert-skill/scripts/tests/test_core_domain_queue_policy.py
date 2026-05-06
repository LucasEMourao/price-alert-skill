"""Tests for extracted queue policies."""

from datetime import datetime, timedelta, timezone

from price_alert_skill.core.domain.queue_policy import (
    begin_scan_run,
    default_queue,
    get_sendable_entries,
    mark_deal_failed,
    prune_expired_entries,
    remove_entry_by_offer_key,
    upsert_pool_deal,
)


def _deal(**overrides):
    base = {
        "title": "Headset Gamer HyperX",
        "url": "https://example.com/p/headset",
        "product_url": "https://example.com/p/headset",
        "marketplace": "amazon_br",
        "current_price": 199.9,
        "previous_price": 299.9,
        "discount_pct": 33.3,
        "savings_brl": 100.0,
        "query": "headset gamer",
        "source_query": "headset gamer",
        "image_url": "https://example.com/headset.jpg",
        "message": "Mensagem",
        "category": "audio_comunicacao",
        "product_key": "example.com/p/headset",
        "offer_key": "example.com/p/headset|199.90",
        "lane": "normal",
    }
    base.update(overrides)
    return base


def test_default_queue_exposes_expected_pool_shape():
    queue = default_queue()

    assert queue["urgent_pool"] == []
    assert queue["priority_pool"] == []
    assert queue["normal_pool"] == []
    assert queue["meta"]["scan_sequence"] == 0


def test_upsert_pool_deal_adds_and_updates_same_offer():
    queue = default_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)

    assert upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence) == "added"
    assert upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence) == "updated"
    assert len(queue["normal_pool"]) == 1
    assert queue["normal_pool"][0]["seen_count"] == 2


def test_upsert_pool_deal_replaces_same_product_with_new_offer():
    queue = default_queue()
    first = _deal(current_price=210.0, discount_pct=30.0, offer_key="example.com/p/headset|210.00")
    second = _deal(
        current_price=150.0,
        discount_pct=50.0,
        savings_brl=149.9,
        lane="priority",
        offer_key="example.com/p/headset|150.00",
    )
    first_scan = begin_scan_run(queue)
    second_scan = begin_scan_run(queue)

    upsert_pool_deal(queue, first, first["lane"], scan_sequence=first_scan)
    result = upsert_pool_deal(queue, second, second["lane"], scan_sequence=second_scan)

    assert result == "replaced_product"
    assert len(queue["priority_pool"]) == 1
    assert queue["priority_pool"][0]["current_price"] == 150.0


def test_prune_expired_entries_respects_time_and_scan_windows():
    now = datetime.now(timezone.utc)
    queue = default_queue()
    stale = (now - timedelta(hours=4)).isoformat()
    queue["urgent_pool"].append({"offer_key": "u1", "last_seen_at": stale, "last_seen_scan": 1})
    queue["priority_pool"].append({"offer_key": "p1", "last_seen_at": stale, "last_seen_scan": 1})
    queue["normal_pool"].append({"offer_key": "n1", "last_seen_at": stale, "last_seen_scan": 1})
    queue["meta"]["scan_sequence"] = 12

    updated = prune_expired_entries(
        queue,
        now=now,
        lane_windows={
            "urgent": (45, 3),
            "priority": (90, 6),
            "normal": (180, 12),
        },
    )

    assert updated["urgent_pool"] == []
    assert updated["priority_pool"] == []
    assert updated["normal_pool"] == []


def test_mark_deal_failed_applies_backoff_and_removes_after_retry_limit():
    queue = default_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence)

    assert mark_deal_failed(queue, deal["offer_key"], retry_backoff_seconds=180, max_send_retries=2) is True
    assert queue["normal_pool"][0]["retry_count"] == 1
    assert queue["normal_pool"][0]["send_after_at"] is not None

    mark_deal_failed(queue, deal["offer_key"], retry_backoff_seconds=180, max_send_retries=0)
    assert queue["normal_pool"] == []


def test_get_sendable_entries_skips_items_still_in_backoff():
    queue = default_queue()
    future = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
    queue["normal_pool"].append({"offer_key": "n1", "send_after_at": future})

    assert get_sendable_entries(queue, "normal") == []


def test_remove_entry_by_offer_key_deletes_deal_from_pool():
    queue = default_queue()
    deal = _deal()
    scan_sequence = begin_scan_run(queue)
    upsert_pool_deal(queue, deal, deal["lane"], scan_sequence=scan_sequence)

    assert remove_entry_by_offer_key(queue, deal["offer_key"]) is True
    assert queue["normal_pool"] == []
