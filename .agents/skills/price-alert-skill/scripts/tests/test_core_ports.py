"""Structural protocol tests for the new application ports."""

from price_alert_skill.core.ports.affiliate_links import AffiliateLinkGenerator
from price_alert_skill.core.ports.clock import Clock, Sleeper
from price_alert_skill.core.ports.message_sender import (
    BatchWhatsAppSender,
    DealChatSender,
    Logger,
    MessageFormatter,
    WhatsAppSessionCloser,
    WhatsAppSessionOpener,
)
from price_alert_skill.core.ports.queue_repository import QueueRepository
from price_alert_skill.core.ports.scanner import DiscountCalculator, MarketplaceRunner
from price_alert_skill.core.ports.sent_deals_repository import SentDealsRepository


class _FakeQueueRepository:
    def load_deal_queue(self):
        return {}

    def save_deal_queue(self, queue):
        return None

    def begin_scan_run(self, queue, now=None):
        return 1

    def mark_sender_tick(self, queue, now=None):
        return queue

    def prune_expired_entries(self, queue, *, now=None):
        return queue

    def upsert_pool_deal(self, queue, deal, lane, *, now=None, scan_sequence=None):
        return "added"

    def remove_entry_by_product_key(self, queue, product_key):
        return True

    def remove_entry_by_offer_key(self, queue, offer_key):
        return True

    def get_sendable_entries(self, queue, lane, *, now=None):
        return []

    def mark_deal_failed(self, queue, offer_key, *, now=None):
        return True


class _FakeSentDealsRepository:
    def load_sent_deals(self):
        return {"sent": {}, "last_cleaned": None}

    def save_sent_deals(self, data):
        return None

    def can_send_again(self, deal, sent_data=None, *, now=None):
        return True

    def filter_new_deals(self, deals, sent_data=None, auto_save=True, mark_as_sent=True):
        return deals, {"sent": {}, "last_cleaned": None}

    def mark_deals_as_sent(self, deals, sent_data=None, auto_save=True):
        return {"sent": {}, "last_cleaned": None}


def _runner(*, query: str, max_results: int):
    return {"products": [], "query": query, "max_results": max_results}


def _discount(current_price: float, list_price: float):
    return 10.0 if list_price > current_price else None


def _affiliate_links(urls: list[str]):
    return {url: url for url in urls}


def _logger(message: str):
    return None


def _formatter(deal: dict):
    return deal.get("title", "")


def _batch_sender(*, deals, group_name, headed, reset_session):
    return {"sent": len(deals), "failed": 0, "errors": []}


def _open_session(*, group_name, headed, reset_session):
    return {"page": object()}


def _close_session(session):
    return None


def _send_chat(page, deal, *, delay_between, max_retries):
    return {"success": True, "title": deal.get("title", ""), "url": deal.get("url", "")}


def _clock():
    return object()


def _sleep(seconds: float):
    return None


def test_repository_ports_are_runtime_checkable():
    assert isinstance(_FakeQueueRepository(), QueueRepository)
    assert isinstance(_FakeSentDealsRepository(), SentDealsRepository)


def test_callable_ports_are_runtime_checkable():
    assert isinstance(_runner, MarketplaceRunner)
    assert isinstance(_discount, DiscountCalculator)
    assert isinstance(_affiliate_links, AffiliateLinkGenerator)
    assert isinstance(_logger, Logger)
    assert isinstance(_formatter, MessageFormatter)
    assert isinstance(_batch_sender, BatchWhatsAppSender)
    assert isinstance(_open_session, WhatsAppSessionOpener)
    assert isinstance(_close_session, WhatsAppSessionCloser)
    assert isinstance(_send_chat, DealChatSender)
    assert isinstance(_clock, Clock)
    assert isinstance(_sleep, Sleeper)
