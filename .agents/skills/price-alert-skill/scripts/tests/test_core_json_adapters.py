"""Tests for JSON repository adapters."""

from datetime import datetime, timezone
from pathlib import Path

from price_alert_skill.core.adapters.json_queue_repository import JSONQueueRepository
from price_alert_skill.core.adapters.json_sent_deals_repository import JSONSentDealsRepository
from price_alert_skill.core.ports.queue_repository import QueueRepository
from price_alert_skill.core.ports.sent_deals_repository import SentDealsRepository


def test_json_queue_repository_is_port_compatible(tmp_path):
    queue_file = tmp_path / "deal_queue.json"
    repo = JSONQueueRepository(
        queue_file_getter=lambda: queue_file,
        cadence_config_getter=lambda: {
            "urgent_window_minutes": 45,
            "urgent_window_scans": 3,
            "priority_window_minutes": 90,
            "priority_window_scans": 6,
            "normal_window_minutes": 180,
            "normal_window_scans": 12,
            "retry_backoff_seconds": 180,
            "max_send_retries": 2,
        },
    )

    assert isinstance(repo, QueueRepository)
    queue = repo.load_deal_queue()
    repo.save_deal_queue(queue)
    assert queue_file.exists()


def test_json_sent_deals_repository_is_port_compatible(tmp_path):
    sent_file = tmp_path / "sent_deals.json"
    repo = JSONSentDealsRepository(
        sent_deals_file_getter=lambda: sent_file,
        cadence_config_getter=lambda: {
            "same_offer_cooldown_hours": 24,
            "urgent_offer_cooldown_hours": 6,
            "min_discount_improvement_points": 5.0,
            "min_savings_improvement_brl": 50.0,
        },
        retention_days_getter=lambda: 7,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert isinstance(repo, SentDealsRepository)
    data = repo.load_sent_deals()
    repo.save_sent_deals(data)
    assert sent_file.exists()

    deal = {
        "url": "https://example.com/p1",
        "offer_key": "offer-1",
        "product_key": "product-1",
        "current_price": 100.0,
    }
    new_deals, sent_data = repo.filter_new_deals([deal], auto_save=False)
    assert len(new_deals) == 1
    assert "offer-1" in repo.mark_deals_as_sent(new_deals, sent_data=sent_data, auto_save=False)["sent"]
