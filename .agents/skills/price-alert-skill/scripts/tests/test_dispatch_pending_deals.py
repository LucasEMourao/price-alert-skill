"""Tests for one-shot dispatch wrapper."""

from unittest.mock import patch

from dispatch_pending_deals import dispatch_pending_deals


@patch(
    "dispatch_pending_deals.run_sender",
    return_value={"sent": 3, "failed": 1, "errors": [], "skipped_due_to_lock": False},
)
def test_dispatch_pending_deals_delegates_to_sender(mock_run_sender):
    results = dispatch_pending_deals(group_name="Grupo", max_messages=6)

    assert results["sent"] == 3
    assert mock_run_sender.call_args.kwargs["group_name"] == "Grupo"
    assert mock_run_sender.call_args.kwargs["continuous"] is False
    assert mock_run_sender.call_args.kwargs["max_messages"] == 6
