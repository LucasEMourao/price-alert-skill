from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.adapters.amazon_scanner import AmazonMarketplaceScanner
from core.adapters.mercadolivre_scanner import MercadoLivreMarketplaceScanner
from core.ports.scanner import MarketplaceRunner


def test_amazon_marketplace_scanner_is_port_compatible(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.adapters.amazon_scanner.amazon_impl.run",
        lambda *, query, max_results: calls.append((query, max_results)) or {"products": []},
    )

    adapter = AmazonMarketplaceScanner()

    assert isinstance(adapter, MarketplaceRunner)
    assert adapter(query="monitor gamer", max_results=5) == {"products": []}
    assert calls == [("monitor gamer", 5)]


def test_mercadolivre_marketplace_scanner_is_port_compatible(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.adapters.mercadolivre_scanner.mercadolivre_impl.run",
        lambda *, query, max_results: calls.append((query, max_results)) or {"products": []},
    )

    adapter = MercadoLivreMarketplaceScanner()

    assert isinstance(adapter, MarketplaceRunner)
    assert adapter(query="placa de video rtx", max_results=7) == {"products": []}
    assert calls == [("placa de video rtx", 7)]
