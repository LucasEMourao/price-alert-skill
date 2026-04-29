from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.entrypoints.dispatch_cli import main as dispatch_cli_main
from core.entrypoints.sender_cli import main as sender_cli_main


def test_sender_cli_invokes_run_sender(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sender_cli.py",
            "--group",
            "Grupo Teste",
            "--continuous",
            "--poll-seconds",
            "11",
            "--max-messages",
            "2",
        ],
    )

    sender_cli_main(
        configure_utf8_stdio_fn=lambda: None,
        resolve_whatsapp_group_fn=lambda value: value,
        run_sender_fn=lambda **kwargs: captured.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        default_poll_seconds=7,
        logger=lambda _message: None,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert captured["group_name"] == "Grupo Teste"
    assert captured["continuous"] is True
    assert captured["poll_seconds"] == 11
    assert captured["max_messages"] == 2


def test_dispatch_cli_invokes_dispatch_use_case(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dispatch_cli.py",
            "--group",
            "Grupo Teste",
            "--max-messages",
            "3",
        ],
    )

    dispatch_cli_main(
        configure_utf8_stdio_fn=lambda: None,
        resolve_whatsapp_group_fn=lambda value: value,
        dispatch_pending_deals_fn=lambda **kwargs: captured.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        logger=lambda _message: None,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert captured["group_name"] == "Grupo Teste"
    assert captured["max_messages"] == 3
    assert captured["headed"] is False
