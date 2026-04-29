"""Tests for the single sender worker."""

from datetime import datetime, timezone
from unittest.mock import patch

from deal_selection import prepare_deal_for_selection
from sender_worker import _acquire_sender_lock, _release_sender_lock, _select_next_deal, run_sender


def _deal(**overrides):
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


def _queue_with(*, urgent=None, priority=None, normal=None):
    return {
        "urgent_pool": urgent or [],
        "priority_pool": priority or [],
        "normal_pool": normal or [],
        "meta": {"last_scan_at": None, "last_sender_tick_at": None, "scan_sequence": 1},
    }


def test_select_next_deal_prefers_urgent_without_advancing_ratio():
    urgent = _deal(
        title="Placa de Video RTX 5080 16GB",
        url="https://example.com/gpu",
        product_url="https://example.com/gpu",
        query="placa de video rtx",
        source_query="placa de video rtx",
        current_price=4999.0,
        previous_price=6999.0,
        discount_pct=40.0,
    )
    urgent["last_seen_at"] = "2026-04-28T00:00:00+00:00"
    urgent["last_seen_scan"] = 1

    queue = _queue_with(urgent=[urgent])
    selected, next_index = _select_next_deal(queue, non_urgent_index=2)

    assert selected["offer_key"] == urgent["offer_key"]
    assert next_index == 2


def test_acquire_sender_lock_replaces_orphan_lock(tmp_path, monkeypatch):
    lock_file = tmp_path / "sender_worker.lock"
    lock_file.write_text("pid=999999 started_at=2026-04-28T18:27:56+00:00", encoding="utf-8")
    monkeypatch.setattr("sender_worker.SENDER_LOCK_FILE", lock_file)
    monkeypatch.setattr("sender_worker._pid_is_running", lambda pid: False)

    fd = _acquire_sender_lock()

    try:
        assert fd is not None
        assert lock_file.exists()
        assert "pid=" in lock_file.read_text(encoding="utf-8")
    finally:
        _release_sender_lock(fd)


@patch("sender_worker.time.sleep", return_value=None)
@patch("sender_worker._release_sender_lock")
@patch("sender_worker._acquire_sender_lock", return_value=123)
@patch("sender_worker.close_whatsapp_session")
@patch("sender_worker.open_whatsapp_session")
@patch(
    "sender_worker.send_deal_in_open_chat",
    return_value={"success": True, "dedup_key": "offer-1", "title": "Produto", "url": "https://example.com"},
)
@patch("sender_worker.mark_deals_as_sent")
@patch("sender_worker.load_sent_deals", return_value={"sent": {}, "last_cleaned": None})
@patch("sender_worker.save_deal_queue")
@patch("sender_worker.load_deal_queue")
def test_run_sender_retries_session_open_in_continuous_mode(
    mock_load_queue,
    _mock_save_queue,
    _mock_load_sent,
    mock_mark_sent,
    _mock_send_deal,
    mock_open_session,
    _mock_close_session,
    _mock_lock,
    _mock_unlock,
    _mock_sleep,
):
    priority = _deal(
        title="Fonte 750W",
        url="https://example.com/fonte",
        product_url="https://example.com/fonte",
        query="fonte 750w",
        source_query="fonte 750w",
        current_price=399.0,
        previous_price=599.0,
        discount_pct=33.0,
    )
    priority["lane"] = "priority"
    priority["offer_key"] = "offer-1"
    priority["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    priority["last_seen_scan"] = 1

    populated_queue = _queue_with(priority=[priority])
    mock_load_queue.side_effect = [populated_queue, populated_queue, populated_queue]
    mock_open_session.side_effect = [RuntimeError("profile busy"), {"page": object()}]

    results = run_sender(group_name="Grupo", continuous=True, max_messages=1, poll_seconds=0)

    assert results["sent"] == 1
    assert mock_open_session.call_count == 2
    assert mock_mark_sent.call_args.args[0][0]["offer_key"] == "offer-1"


@patch("sender_worker._stop_requested", side_effect=[True])
@patch("sender_worker._release_sender_lock")
@patch("sender_worker._acquire_sender_lock", return_value=123)
@patch("sender_worker.close_whatsapp_session")
def test_run_sender_honors_stop_request_before_processing(
    _mock_close_session,
    _mock_lock,
    _mock_unlock,
    _mock_stop_requested,
):
    results = run_sender(group_name="Grupo", continuous=True, poll_seconds=0)

    assert results["sent"] == 0
    assert results["failed"] == 0


@patch("sender_worker._release_sender_lock")
@patch("sender_worker._acquire_sender_lock", return_value=123)
@patch("sender_worker.close_whatsapp_session")
@patch("sender_worker.open_whatsapp_session", return_value={"page": object()})
@patch(
    "sender_worker.send_deal_in_open_chat",
    return_value={"success": True, "dedup_key": "offer-1", "title": "Produto", "url": "https://example.com"},
)
@patch("sender_worker.mark_deals_as_sent")
@patch("sender_worker.load_sent_deals", return_value={"sent": {}, "last_cleaned": None})
@patch("sender_worker.save_deal_queue")
@patch("sender_worker.load_deal_queue")
def test_run_sender_processes_one_message_and_exits(
    mock_load_queue,
    _mock_save_queue,
    _mock_load_sent,
    mock_mark_sent,
    _mock_send_deal,
    mock_open_session,
    _mock_close_session,
    _mock_lock,
    _mock_unlock,
):
    priority = _deal(
        title="Fonte 750W",
        url="https://example.com/fonte",
        product_url="https://example.com/fonte",
        query="fonte 750w",
        source_query="fonte 750w",
        current_price=399.0,
        previous_price=599.0,
        discount_pct=33.0,
    )
    priority["lane"] = "priority"
    priority["offer_key"] = "offer-1"
    priority["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    priority["last_seen_scan"] = 1

    empty_queue = _queue_with()
    populated_queue = _queue_with(priority=[priority])
    mock_load_queue.side_effect = [populated_queue, populated_queue, empty_queue]

    results = run_sender(group_name="Grupo", max_messages=1)

    assert results["sent"] == 1
    assert mock_open_session.called
    assert mock_mark_sent.call_args.args[0][0]["offer_key"] == "offer-1"
