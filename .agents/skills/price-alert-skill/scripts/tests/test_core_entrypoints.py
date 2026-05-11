from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from price_alert_skill.core.entrypoints.dispatch_cli import main as dispatch_cli_main
from price_alert_skill.core.entrypoints.scan_cli import main as scan_cli_main
from price_alert_skill.core.entrypoints.sender_cli import main as sender_cli_main


def test_sender_cli_invokes_run_sender(monkeypatch):
    captured = {}
    logs: list[str] = []
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
            "--profile",
            "beauty",
        ],
    )

    sender_cli_main(
        configure_utf8_stdio_fn=lambda: None,
        resolve_whatsapp_group_fn=lambda value: value,
        run_sender_fn=lambda **kwargs: captured.update(kwargs) or {"sent": 1, "failed": 0, "errors": []},
        default_poll_seconds=7,
        logger=logs.append,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert captured["group_name"] == "Grupo Teste"
    assert captured["continuous"] is True
    assert captured["poll_seconds"] == 11
    assert captured["max_messages"] == 2
    assert captured["product_profile"] == "beauty"
    assert logs[0].startswith("[2026-04-29 09:00:00] Starting sender worker...")


def test_dispatch_cli_invokes_dispatch_use_case(monkeypatch):
    captured = {}
    logs: list[str] = []
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
        logger=logs.append,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert captured["group_name"] == "Grupo Teste"
    assert captured["max_messages"] == 3
    assert captured["headed"] is False
    assert logs[0].startswith("[2026-04-29 09:00:00] Dispatching queued deals...")


def test_scan_cli_passes_selected_profile_to_all_queries(monkeypatch):
    captured = {}
    logs: list[str] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scan_cli.py",
            "--all",
            "--profile",
            "beauty",
            "--query-categories",
            "beleza_perfumes",
            "--scan-only",
        ],
    )

    scan_cli_main(
        configure_utf8_stdio_fn=lambda: None,
        get_queries_fn=lambda profile, categories: captured.update(
            {"profile": profile, "categories": categories}
        )
        or ["perfume feminino"],
        scan_all_fn=lambda max_results, min_discount, marketplaces, queries: captured.update(
            {
                "max_results": max_results,
                "min_discount": min_discount,
                "marketplaces": marketplaces,
                "queries": queries,
            }
        )
        or [],
        deduplicate_run_deals_fn=lambda deals: deals,
        prepare_deal_for_selection_fn=lambda deal: deal,
        apply_affiliate_links_fn=lambda deals: None,
        handle_cadence_scan_fn=lambda parser, deals, args, now: captured.update({"scan_only": args.scan_only}),
        handle_legacy_flow_fn=lambda parser, deals, args, now: captured.update({"legacy": True}),
        logger=logs.append,
        now_fn=lambda: datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert captured["profile"] == "beauty"
    assert captured["categories"] == "beleza_perfumes"
    assert captured["queries"] == ["perfume feminino"]
    assert captured["marketplaces"] == ["amazon_br", "mercadolivre_br"]
    assert captured["scan_only"] is True
    assert "legacy" not in captured
    assert logs[0].startswith("[2026-04-29 09:00:00] Scanning for deals (min 10.0% off)...")
