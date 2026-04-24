"""Tests for cadence batch dispatch."""

from unittest.mock import patch

from dispatch_pending_deals import dispatch_pending_deals
from deal_selection import prepare_deal_for_selection


def _queue_deal(**overrides):
    base = {
        "title": "Monitor Gamer",
        "url": "https://example.com/monitor",
        "product_url": "https://example.com/monitor",
        "marketplace": "amazon_br",
        "current_price": 799.0,
        "previous_price": 999.0,
        "discount_pct": 20.0,
        "query": "monitor gamer",
        "source_query": "monitor gamer",
        "image_url": "https://example.com/monitor.jpg",
        "message": "Mensagem",
    }
    base.update(overrides)
    return prepare_deal_for_selection(base)


@patch("dispatch_pending_deals.save_deal_queue")
@patch("dispatch_pending_deals.mark_deals_as_sent")
@patch("dispatch_pending_deals.load_sent_deals", return_value={"sent": {}, "last_cleaned": None})
@patch(
    "dispatch_pending_deals.send_deals_to_whatsapp",
    return_value={"sent": 2, "failed": 0, "errors": [], "successful_keys": ["urgent-1", "normal-1"]},
)
@patch(
    "dispatch_pending_deals.load_deal_queue",
)
def test_dispatch_pending_deals_sends_urgent_then_normal(
    mock_load_queue,
    _mock_send,
    _mock_load_sent,
    mock_mark_sent,
    _mock_save_queue,
):
    urgent = _queue_deal(
        title="GPU Super",
        url="https://example.com/gpu",
        product_url="https://example.com/gpu",
        query="placa de video rtx",
        source_query="placa de video rtx",
    )
    urgent["offer_key"] = "urgent-1"
    urgent["is_super_promo"] = True

    normal = _queue_deal()
    normal["offer_key"] = "normal-1"

    mock_load_queue.return_value = {
        "normal": [normal],
        "urgent_retry": [urgent],
        "meta": {},
    }

    results = dispatch_pending_deals(group_name="Grupo")

    assert results["sent"] == 2
    sent_deals = mock_mark_sent.call_args.args[0]
    assert [deal["offer_key"] for deal in sent_deals] == ["urgent-1", "normal-1"]
