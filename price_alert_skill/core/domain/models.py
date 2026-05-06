"""Core domain models used by the application and adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import ActiveLane, Lane, QueueStatus


_DEAL_FIELDS = {
    "title",
    "url",
    "product_url",
    "marketplace",
    "query",
    "source_query",
    "category",
    "lane",
    "current_price",
    "previous_price",
    "discount_pct",
    "savings_brl",
    "product_key",
    "offer_key",
    "image_url",
    "message",
    "is_super_promo",
    "quality_passed",
}

_QUEUE_FIELDS = {
    "queue_kind",
    "status",
    "first_seen_at",
    "last_seen_at",
    "first_seen_scan",
    "last_seen_scan",
    "seen_count",
    "retry_count",
    "send_after_at",
    "last_send_attempt_at",
}


@dataclass(slots=True)
class Deal:
    """Normalized representation of an offer independent from persistence details."""

    title: str
    url: str
    product_url: str
    marketplace: str
    query: str = ""
    source_query: str = ""
    category: str = ""
    lane: Lane = "discarded"
    current_price: float | None = None
    previous_price: float | None = None
    discount_pct: float = 0.0
    savings_brl: float = 0.0
    product_key: str = ""
    offer_key: str = ""
    image_url: str | None = None
    message: str | None = None
    is_super_promo: bool = False
    quality_passed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Deal":
        """Build a deal from the current dict-based project shape."""
        known = {key: data.get(key) for key in _DEAL_FIELDS}
        metadata = {
            key: value
            for key, value in data.items()
            if key not in _DEAL_FIELDS and key not in _QUEUE_FIELDS
        }
        return cls(
            title=str(known.get("title") or ""),
            url=str(known.get("url") or ""),
            product_url=str(known.get("product_url") or known.get("url") or ""),
            marketplace=str(known.get("marketplace") or ""),
            query=str(known.get("query") or ""),
            source_query=str(known.get("source_query") or ""),
            category=str(known.get("category") or ""),
            lane=str(known.get("lane") or "discarded"),  # type: ignore[arg-type]
            current_price=(
                float(known["current_price"])
                if known.get("current_price") is not None
                else None
            ),
            previous_price=(
                float(known["previous_price"])
                if known.get("previous_price") is not None
                else None
            ),
            discount_pct=float(known.get("discount_pct") or 0.0),
            savings_brl=float(known.get("savings_brl") or 0.0),
            product_key=str(known.get("product_key") or ""),
            offer_key=str(known.get("offer_key") or ""),
            image_url=known.get("image_url"),
            message=known.get("message"),
            is_super_promo=bool(known.get("is_super_promo", False)),
            quality_passed=bool(known.get("quality_passed", True)),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the domain model back to the current dict-based shape."""
        payload = dict(self.metadata)
        payload.update(
            {
                "title": self.title,
                "url": self.url,
                "product_url": self.product_url,
                "marketplace": self.marketplace,
                "query": self.query,
                "source_query": self.source_query,
                "category": self.category,
                "lane": self.lane,
                "current_price": self.current_price,
                "previous_price": self.previous_price,
                "discount_pct": self.discount_pct,
                "savings_brl": self.savings_brl,
                "product_key": self.product_key,
                "offer_key": self.offer_key,
                "image_url": self.image_url,
                "message": self.message,
                "is_super_promo": self.is_super_promo,
                "quality_passed": self.quality_passed,
            }
        )
        return payload


@dataclass(slots=True)
class QueueItem:
    """A queued delivery candidate plus sender-specific state."""

    deal: Deal
    lane: ActiveLane
    queue_kind: ActiveLane
    status: QueueStatus = "pending"
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    first_seen_scan: int = 0
    last_seen_scan: int = 0
    seen_count: int = 1
    retry_count: int = 0
    send_after_at: str | None = None
    last_send_attempt_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def offer_key(self) -> str:
        return self.deal.offer_key

    @property
    def product_key(self) -> str:
        return self.deal.product_key

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "QueueItem":
        """Build a queue item from the persisted queue shape."""
        deal = Deal.from_mapping(data)
        metadata = {
            key: value
            for key, value in data.items()
            if key not in _DEAL_FIELDS and key not in _QUEUE_FIELDS
        }
        lane = str(data.get("lane") or data.get("queue_kind") or "normal")
        return cls(
            deal=deal,
            lane=lane,  # type: ignore[arg-type]
            queue_kind=str(data.get("queue_kind") or lane),  # type: ignore[arg-type]
            status=str(data.get("status") or "pending"),  # type: ignore[arg-type]
            first_seen_at=data.get("first_seen_at"),
            last_seen_at=data.get("last_seen_at"),
            first_seen_scan=int(data.get("first_seen_scan", 0) or 0),
            last_seen_scan=int(data.get("last_seen_scan", 0) or 0),
            seen_count=int(data.get("seen_count", 1) or 1),
            retry_count=int(data.get("retry_count", 0) or 0),
            send_after_at=data.get("send_after_at"),
            last_send_attempt_at=data.get("last_send_attempt_at"),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the queue item back to the current persisted shape."""
        payload = self.deal.to_dict()
        payload.update(self.metadata)
        payload.update(
            {
                "lane": self.lane,
                "queue_kind": self.queue_kind,
                "status": self.status,
                "first_seen_at": self.first_seen_at,
                "last_seen_at": self.last_seen_at,
                "first_seen_scan": self.first_seen_scan,
                "last_seen_scan": self.last_seen_scan,
                "seen_count": self.seen_count,
                "retry_count": self.retry_count,
                "send_after_at": self.send_after_at,
                "last_send_attempt_at": self.last_send_attempt_at,
            }
        )
        return payload
