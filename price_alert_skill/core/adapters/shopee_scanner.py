"""Shopee ``productOfferV2`` scanner and normalization adapter.

The scanner owns the provider-specific GraphQL shape.  It intentionally stops
at a normalized product payload and does not know about queues, deal lanes, or
WhatsApp delivery.
"""

from __future__ import annotations

import copy
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from price_alert_skill import config
from price_alert_skill.core.adapters.shopee_api import (
    ShopeeApiError,
    ShopeeConfigurationError,
    ShopeeErrorKind,
    ShopeeGraphQLClient,
    classify_shopee_error,
    parse_graphql_errors,
    redact_secrets,
)


SHOPEE_MARKETPLACE = "shopee_br"
DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGES = 5
PRICE_DISCOUNT_SOURCE = "shopee_price_discount_rate"

# Keep the field selection explicit.  In particular, priceMax is requested for
# raw diagnostics only and is never interpreted as a previous/list price.
PRODUCT_OFFER_V2_QUERY = """query ProductOfferV2($page: Int!, $limit: Int!, $keyword: String!) {
  productOfferV2(page: $page, limit: $limit, keyword: $keyword) {
    nodes {
      itemId
      commissionRate
      sellerCommissionRate
      shopeeCommissionRate
      commission
      price
      sales
      priceMax
      priceMin
      productCatIds
      ratingStar
      priceDiscountRate
      imageUrl
      productName
      shopId
      shopName
      shopType
      productLink
      offerLink
      periodStartTime
      periodEndTime
    }
    pageInfo {
      page
      limit
      hasNextPage
      scrollId
    }
  }
}"""


# A named mapping makes the boundary explicit: the project's search query is
# the Shopee keyword.  Unknown/custom queries deliberately use the same rule.
PROJECT_QUERY_TO_SHOPEE_KEYWORD: dict[str, str] = {}


@dataclass(frozen=True)
class ShopeeProviderError:
    """Structured, redacted scanner failure suitable for result payloads."""

    kind: str
    message: str
    code: int | str | None = None
    status_code: int | None = None
    page: int | None = None
    retryable: bool = False
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": SHOPEE_MARKETPLACE,
            "kind": self.kind,
            "message": self.message,
            "code": self.code,
            "status_code": self.status_code,
            "page": self.page,
            "retryable": self.retryable,
            **({"field": self.field} if self.field else {}),
        }


class ShopeeScannerError(RuntimeError):
    """Exception form of a scanner failure for callers that need one."""

    def __init__(self, failure: ShopeeProviderError):
        self.failure = failure
        super().__init__(failure.message)


def map_query_to_keyword(query: str) -> str:
    """Map one project search query to the provider's keyword argument."""
    if not isinstance(query, str):
        raise ValueError("Shopee query must be a string")

    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Shopee query must not be empty")

    return PROJECT_QUERY_TO_SHOPEE_KEYWORD.get(
        normalized_query.lower(), normalized_query
    )


# Descriptive aliases are useful to callers without creating another mapping
# policy.
project_query_to_keyword = map_query_to_keyword
map_query_to_shopee_keyword = map_query_to_keyword
query_to_keyword = map_query_to_keyword


def build_product_offer_query(
    *,
    page: int,
    keyword: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Build one signed-client payload for ``productOfferV2``.

    ``page`` and ``keyword`` are sent as GraphQL variables.  This keeps the
    query stable while ensuring the exact variable values are included in the
    payload signed by :class:`ShopeeGraphQLClient`.
    """
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("Shopee page must be an integer greater than zero")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Shopee page limit must be an integer greater than zero")
    if keyword is not None and query is not None:
        raise ValueError("keyword and query cannot both be provided")
    normalized_keyword = map_query_to_keyword(
        keyword if keyword is not None else query or ""
    )
    return {
        "query": PRODUCT_OFFER_V2_QUERY,
        "operationName": "ProductOfferV2",
        "variables": {
            "page": page,
            "limit": limit,
            "keyword": normalized_keyword,
        },
    }


build_product_offer_v2_query = build_product_offer_query
build_product_offer_v2_payload = build_product_offer_query
build_product_offer_payload = build_product_offer_query


def _parse_decimal(value: Any, *, positive: bool = False) -> float | None:
    """Parse finite provider numerics without accepting booleans or junk."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    if not parsed.is_finite() or (positive and parsed <= 0):
        return None
    result = float(parsed)
    return result if math.isfinite(result) else None


def _parse_integer(value: Any) -> int | None:
    """Parse an integer epoch/id-like value conservatively."""
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        return None
    try:
        return int(parsed)
    except (OverflowError, ValueError):
        return None


def _valid_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _invalid_node_error(
    reason: str,
    *,
    page: int | None,
    field: str | None = None,
) -> dict[str, Any]:
    return ShopeeProviderError(
        kind="normalization",
        message=reason,
        page=page,
        field=field,
    ).to_dict()


def _normalize_node(
    node: Mapping[str, Any],
    *,
    now: int | float,
    page: int | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Normalize one node and return product plus non-fatal diagnostics."""
    diagnostics: list[dict[str, Any]] = []

    title = node.get("productName")
    if not isinstance(title, str) or not title.strip():
        return None, [_invalid_node_error("productName is required", page=page, field="productName")]
    title = title.strip()

    product_url = _valid_http_url(node.get("productLink"))
    if product_url is None:
        return None, [_invalid_node_error("productLink is required and must be an HTTP URL", page=page, field="productLink")]

    offer_url = _valid_http_url(node.get("offerLink"))
    if offer_url is None:
        return None, [_invalid_node_error("offerLink is required and must be an HTTP URL", page=page, field="offerLink")]

    price_min_raw = node.get("priceMin")
    price_raw = node.get("price")
    price_min = _parse_decimal(price_min_raw, positive=True)
    price = _parse_decimal(price_raw, positive=True)

    if price_min_raw is not None and price_min is None:
        diagnostics.append(
            _invalid_node_error("priceMin is not a valid positive number; price was used", page=page, field="priceMin")
        )
    if price_raw is not None and price is None:
        diagnostics.append(
            _invalid_node_error("price is not a valid positive number", page=page, field="price")
        )

    current_price = price_min if price_min is not None else price
    if current_price is None:
        return None, diagnostics + [
            _invalid_node_error("a valid positive priceMin or price is required", page=page, field="priceMin")
        ]

    price_discrepancy: dict[str, Any] | None = None
    if price_min is not None and price is not None and not math.isclose(
        price_min,
        price,
        rel_tol=0.0,
        abs_tol=0.005,
    ):
        price_discrepancy = {
            "type": "price_discrepancy",
            "price_min": price_min,
            "price": price,
        }
        diagnostics.append({**price_discrepancy, "page": page})

    discount_raw = node.get("priceDiscountRate")
    discount_pct = _parse_decimal(discount_raw)
    if discount_pct is None or not 0 <= discount_pct <= 100:
        return None, diagnostics + [
            _invalid_node_error(
                "priceDiscountRate must be numeric and within 0..100",
                page=page,
                field="priceDiscountRate",
            )
        ]

    period_start_raw = node.get("periodStartTime")
    period_end_raw = node.get("periodEndTime")
    period_start = _parse_integer(period_start_raw)
    period_end = _parse_integer(period_end_raw)

    if period_start_raw is not None and period_start is None:
        return None, diagnostics + [
            _invalid_node_error("periodStartTime is not a valid Unix timestamp", page=page, field="periodStartTime")
        ]
    if period_end_raw is not None and period_end is None:
        return None, diagnostics + [
            _invalid_node_error("periodEndTime is not a valid Unix timestamp", page=page, field="periodEndTime")
        ]
    if period_start is not None and period_end is not None and period_start > period_end:
        return None, diagnostics + [
            _invalid_node_error("periodStartTime cannot be after periodEndTime", page=page, field="periodStartTime")
        ]

    current_timestamp = float(now)
    if period_start is not None and period_start > current_timestamp:
        return None, diagnostics
    if period_end is not None and period_end < current_timestamp:
        return None, diagnostics

    raw_rating = node.get("ratingStar")
    rating = _parse_decimal(raw_rating)
    if rating is not None and rating <= 0:
        rating = None
    elif raw_rating not in (None, "") and rating is None:
        diagnostics.append(
            _invalid_node_error("ratingStar is not a valid number", page=page, field="ratingStar")
        )

    raw_shop_type = node.get("shopType")
    if isinstance(raw_shop_type, list):
        shop_type = copy.deepcopy(raw_shop_type)
    else:
        shop_type = []
        if raw_shop_type is not None:
            diagnostics.append(
                _invalid_node_error("shopType must be a list; retained as unknown", page=page, field="shopType")
            )

    raw_categories = node.get("productCatIds")
    if isinstance(raw_categories, list):
        product_cat_ids = copy.deepcopy(raw_categories)
    else:
        product_cat_ids = []
        if raw_categories is not None:
            diagnostics.append(
                _invalid_node_error("productCatIds must be a list", page=page, field="productCatIds")
            )

    raw_item_id = node.get("itemId")
    item_id = raw_item_id if not isinstance(raw_item_id, bool) else None
    raw_metadata = copy.deepcopy(dict(node))

    product: dict[str, Any] = {
        "marketplace": SHOPEE_MARKETPLACE,
        "title": title,
        # ``url`` is the outbound/affiliate URL.  ``product_url`` remains the
        # canonical source URL and is never replaced by offerLink.
        "url": offer_url,
        "product_url": product_url,
        "offer_link": offer_url,
        "product_link": product_url,
        "price": current_price,
        "current_price": current_price,
        "price_min": price_min,
        "price_max": _parse_decimal(node.get("priceMax"), positive=True),
        "list_price": None,
        "previous_price": None,
        "savings_brl": None,
        "discount_pct": discount_pct,
        "price_discount_rate": discount_pct,
        "discount_source": PRICE_DISCOUNT_SOURCE,
        "price_discount_source": PRICE_DISCOUNT_SOURCE,
        "item_id": item_id,
        "shop_id": node.get("shopId"),
        "shop_name": node.get("shopName"),
        "shop_type": shop_type,
        "image_url": node.get("imageUrl") if isinstance(node.get("imageUrl"), str) else None,
        "sales": node.get("sales"),
        "rating": rating,
        "rating_star": rating,
        "product_cat_ids": product_cat_ids,
        "period_start_time": period_start,
        "period_end_time": period_end,
        # Keep all provider names and values available to diagnostics and a
        # later source-aware application policy.
        "raw": raw_metadata,
        "raw_metadata": copy.deepcopy(raw_metadata),
        "metadata": copy.deepcopy(raw_metadata),
    }
    if item_id is not None:
        product["source_item_id"] = item_id

    if price_discrepancy is not None:
        product["price_discrepancy"] = price_discrepancy
    if diagnostics:
        product["diagnostics"] = diagnostics

    return product, diagnostics


def normalize_product_node(
    node: Mapping[str, Any],
    *,
    now: int | float | None = None,
) -> dict[str, Any] | None:
    """Normalize a single product node, returning ``None`` when unusable."""
    if not isinstance(node, Mapping):
        return None
    product, _diagnostics = _normalize_node(
        node,
        now=time.time() if now is None else now,
        page=None,
    )
    return product


normalize_product = normalize_product_node


def _identity_key(product: Mapping[str, Any]) -> str:
    item_id = product.get("item_id")
    if item_id is not None and not isinstance(item_id, bool) and str(item_id).strip():
        return f"item:{item_id}"

    product_url = str(product.get("product_url") or "").strip().lower()
    parsed = urlparse(product_url)
    canonical_url = f"{parsed.netloc}{parsed.path.rstrip('/')}" if parsed.netloc else product_url
    return f"url:{canonical_url}"


def _scanner_error_from_exception(
    error: Exception,
    *,
    page: int | None,
) -> dict[str, Any]:
    if isinstance(error, ShopeeApiError):
        return ShopeeProviderError(
            kind=error.category,
            message=redact_secrets(error.message),
            code=error.code,
            status_code=error.status_code,
            page=page,
            retryable=error.retryable,
        ).to_dict()
    if isinstance(error, ShopeeConfigurationError):
        return ShopeeProviderError(
            kind=ShopeeErrorKind.CONFIGURATION.value,
            message=redact_secrets(str(error)),
            page=page,
        ).to_dict()

    return ShopeeProviderError(
        kind="scanner",
        message=redact_secrets(f"{type(error).__name__}: {error}"),
        page=page,
    ).to_dict()


class ShopeeMarketplaceScanner:
    """Fetch and normalize Shopee product offers through the Sprint 1 client."""

    def __init__(
        self,
        client: ShopeeGraphQLClient | Any | None = None,
        *,
        api_client: ShopeeGraphQLClient | Any | None = None,
        max_pages: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        clock: Callable[[], int | float] | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        if max_pages is not None and (
            isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1
        ):
            raise ValueError("max_pages must be an integer greater than zero")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
            raise ValueError("page_size must be an integer greater than zero")

        if client is not None and api_client is not None:
            raise ValueError("pass either client or api_client, not both")
        self.client = api_client if api_client is not None else client
        self.max_pages = max_pages
        self.page_size = page_size
        self.clock = clock or time.time
        self.logger = logger

    def __call__(self, *, query: str, max_results: int) -> dict[str, Any]:
        return self.run(query=query, max_results=max_results)

    def run(self, *, query: str, max_results: int) -> dict[str, Any]:
        """Return a provider-shaped payload with normalized products/errors."""
        result: dict[str, Any] = {
            "marketplace": SHOPEE_MARKETPLACE,
            "query": query if isinstance(query, str) else "",
            "keyword": None,
            "products": [],
            "errors": [],
            "diagnostics": [],
            "pages": [],
            "partial": False,
            "truncated": False,
        }

        try:
            keyword = map_query_to_keyword(query)
        except (TypeError, ValueError) as exc:
            result["errors"].append(
                ShopeeProviderError(kind="validation", message=str(exc)).to_dict()
            )
            return result

        result["query"] = query.strip()
        result["keyword"] = keyword
        if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
            result["errors"].append(
                ShopeeProviderError(
                    kind="validation",
                    message="max_results must be an integer greater than zero",
                ).to_dict()
            )
            return result

        configured_max_pages = config.resolve_shopee_settings().max_pages_per_query
        max_pages = self.max_pages if self.max_pages is not None else configured_max_pages
        max_pages = max(1, int(max_pages or DEFAULT_MAX_PAGES))
        request_limit = min(self.page_size, max_results)
        now = self.clock()

        client = self.client
        if client is None:
            try:
                client = ShopeeGraphQLClient()
            except Exception as exc:  # configuration errors are provider failures
                result["errors"].append(_scanner_error_from_exception(exc, page=None))
                return result

        seen: set[str] = set()
        page = 1
        has_next_page = False

        while page <= max_pages and len(result["products"]) < max_results:
            payload = build_product_offer_query(
                page=page,
                keyword=keyword,
                limit=request_limit,
            )
            try:
                response = client.execute(payload)
            except Exception as exc:  # the client provides redacted structured errors
                result["errors"].append(_scanner_error_from_exception(exc, page=page))
                result["partial"] = bool(result["products"])
                break

            if not isinstance(response, Mapping):
                result["errors"].append(
                    ShopeeProviderError(
                        kind="response",
                        message="Shopee response was not a JSON object",
                        page=page,
                    ).to_dict()
                )
                result["partial"] = bool(result["products"])
                break

            graphql_errors = parse_graphql_errors(response)
            if graphql_errors:
                for graphql_error in graphql_errors:
                    classification = classify_shopee_error(
                        graphql_error.code,
                        graphql_error.message,
                        status_code=200,
                    )
                    result["errors"].append(
                        ShopeeProviderError(
                            kind=classification.category,
                            message=redact_secrets(graphql_error.message),
                            code=graphql_error.code,
                            status_code=200,
                            page=page,
                            retryable=classification.retryable,
                        ).to_dict()
                    )

            # A normal HTTP-200 GraphQL failure has no usable operation data.
            # The provider error above is the actionable failure; avoid adding
            # a misleading second schema error for the expected ``data: null``
            # shape.  A data+errors response is handled as a partial page.
            raw_data = response.get("data")
            if graphql_errors and not (
                isinstance(raw_data, Mapping)
                and isinstance(raw_data.get("productOfferV2"), Mapping)
            ):
                result["partial"] = bool(result["products"])
                break

            connection = self._extract_connection(response, page=page, result=result)
            if connection is None:
                result["partial"] = bool(result["products"])
                break

            raw_nodes = connection.get("nodes")
            if raw_nodes is None:
                raw_nodes = []
            if not isinstance(raw_nodes, list):
                result["errors"].append(
                    ShopeeProviderError(
                        kind="response",
                        message="productOfferV2.nodes was not a JSON array",
                        page=page,
                        field="nodes",
                    ).to_dict()
                )
                result["partial"] = bool(result["products"])
                break

            page_info = connection.get("pageInfo")
            if not isinstance(page_info, Mapping):
                page_info = {}
                result["errors"].append(
                    ShopeeProviderError(
                        kind="response",
                        message="productOfferV2.pageInfo was missing or invalid",
                        page=page,
                        field="pageInfo",
                    ).to_dict()
                )

            raw_has_next = page_info.get("hasNextPage", False)
            if not isinstance(raw_has_next, bool):
                result["errors"].append(
                    ShopeeProviderError(
                        kind="response",
                        message="pageInfo.hasNextPage was not boolean",
                        page=page,
                        field="hasNextPage",
                    ).to_dict()
                )
                raw_has_next = False
            has_next_page = raw_has_next

            response_page = page_info.get("page")
            response_page_number = _parse_integer(response_page)
            result["pages"].append(
                {
                    "requested_page": page,
                    "response_page": response_page_number,
                    "limit": page_info.get("limit"),
                    "has_next_page": has_next_page,
                    # scrollId is retained for diagnostics, never sent back.
                    "scroll_id": copy.deepcopy(page_info.get("scrollId")),
                    "node_count": len(raw_nodes),
                }
            )

            for node in raw_nodes:
                if not isinstance(node, Mapping):
                    result["errors"].append(
                        _invalid_node_error(
                            "productOfferV2 node was not a JSON object",
                            page=page,
                        )
                    )
                    continue

                product, node_diagnostics = _normalize_node(
                    node,
                    now=now,
                    page=page,
                )
                if product is None:
                    result["errors"].extend(node_diagnostics)
                    continue

                identity = _identity_key(product)
                if identity in seen:
                    result["diagnostics"].append(
                        {
                            "type": "duplicate_product",
                            "page": page,
                            "item_id": product.get("item_id"),
                            "product_url": product.get("product_url"),
                        }
                    )
                    continue
                seen.add(identity)
                result["products"].append(product)
                for diagnostic in node_diagnostics:
                    if diagnostic.get("kind") != "normalization":
                        result["diagnostics"].append(diagnostic)
                if len(result["products"]) >= max_results:
                    break

            if graphql_errors:
                # The API client normally raises before this point.  A fake or
                # alternate client may return a partial HTTP-200 body; retain
                # usable nodes but never claim a complete scan or paginate it.
                result["partial"] = True
                break
            if not has_next_page:
                break
            page += 1

        if has_next_page and page >= max_pages and len(result["products"]) < max_results:
            result["truncated"] = True
            result["partial"] = True
            result["errors"].append(
                ShopeeProviderError(
                    kind="pagination",
                    message="SHOPEE_MAX_PAGES_PER_QUERY safety limit reached",
                    page=max_pages,
                    code="page_safety_limit",
                ).to_dict()
            )

        if len(result["products"]) >= max_results and has_next_page:
            result["truncated"] = True

        return result

    # Alias used by adapters that prefer an explicit method name.
    scan = run

    @staticmethod
    def _extract_connection(
        response: Mapping[str, Any],
        *,
        page: int,
        result: dict[str, Any],
    ) -> Mapping[str, Any] | None:
        data = response.get("data")
        if not isinstance(data, Mapping):
            result["errors"].append(
                ShopeeProviderError(
                    kind="response",
                    message="Shopee response did not contain a usable data object",
                    page=page,
                ).to_dict()
            )
            return None

        connection = data.get("productOfferV2")
        if not isinstance(connection, Mapping):
            result["errors"].append(
                ShopeeProviderError(
                    kind="response",
                    message="Shopee response did not contain productOfferV2 data",
                    page=page,
                ).to_dict()
            )
            return None
        return connection


ShopeeScanner = ShopeeMarketplaceScanner
