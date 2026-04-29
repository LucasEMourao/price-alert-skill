"""Tests for the new pure domain models."""

from core.domain.models import Deal, QueueItem


def test_deal_from_mapping_keeps_core_fields_and_extra_metadata():
    data = {
        "title": "Headset Gamer HyperX",
        "url": "https://example.com/p/headset",
        "product_url": "https://example.com/p/headset",
        "marketplace": "amazon_br",
        "query": "headset gamer",
        "source_query": "headset gamer",
        "category": "audio_comunicacao",
        "lane": "priority",
        "current_price": 199.9,
        "previous_price": 299.9,
        "discount_pct": 33.3,
        "savings_brl": 100.0,
        "product_key": "example.com/p/headset",
        "offer_key": "example.com/p/headset|199.90",
        "image_url": "https://example.com/image.jpg",
        "message": "Mensagem",
        "quality_passed": True,
        "sponsored": False,
    }

    deal = Deal.from_mapping(data)

    assert deal.title == "Headset Gamer HyperX"
    assert deal.marketplace == "amazon_br"
    assert deal.lane == "priority"
    assert deal.savings_brl == 100.0
    assert deal.metadata == {"sponsored": False}


def test_deal_to_dict_round_trips_back_to_mapping_shape():
    deal = Deal.from_mapping(
        {
            "title": "Monitor Gamer",
            "url": "https://example.com/monitor",
            "product_url": "https://example.com/monitor",
            "marketplace": "mercadolivre_br",
            "lane": "urgent",
            "current_price": 899.0,
            "discount_pct": 40.0,
            "custom_note": "top deal",
        }
    )

    payload = deal.to_dict()

    assert payload["title"] == "Monitor Gamer"
    assert payload["lane"] == "urgent"
    assert payload["current_price"] == 899.0
    assert payload["custom_note"] == "top deal"


def test_queue_item_from_mapping_wraps_deal_and_queue_fields():
    data = {
        "title": "SSD NVMe 1TB",
        "url": "https://example.com/ssd",
        "product_url": "https://example.com/ssd",
        "marketplace": "amazon_br",
        "lane": "priority",
        "queue_kind": "priority",
        "offer_key": "ssd|299.90",
        "product_key": "ssd",
        "status": "pending",
        "first_seen_at": "2026-04-29T10:00:00+00:00",
        "last_seen_at": "2026-04-29T10:15:00+00:00",
        "first_seen_scan": 11,
        "last_seen_scan": 12,
        "seen_count": 2,
        "retry_count": 1,
        "send_after_at": "2026-04-29T10:18:00+00:00",
        "source": "scan",
    }

    item = QueueItem.from_mapping(data)

    assert item.deal.title == "SSD NVMe 1TB"
    assert item.lane == "priority"
    assert item.queue_kind == "priority"
    assert item.seen_count == 2
    assert item.retry_count == 1
    assert item.metadata == {"source": "scan"}


def test_queue_item_to_dict_preserves_current_persisted_shape():
    item = QueueItem.from_mapping(
        {
            "title": "Ryzen 7",
            "url": "https://example.com/cpu",
            "product_url": "https://example.com/cpu",
            "marketplace": "amazon_br",
            "lane": "urgent",
            "queue_kind": "urgent",
            "offer_key": "cpu|1599.00",
            "product_key": "cpu",
            "status": "pending",
            "tag": "featured",
        }
    )

    payload = item.to_dict()

    assert payload["title"] == "Ryzen 7"
    assert payload["lane"] == "urgent"
    assert payload["queue_kind"] == "urgent"
    assert payload["status"] == "pending"
    assert payload["tag"] == "featured"
