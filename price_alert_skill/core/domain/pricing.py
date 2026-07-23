"""Pure pricing policies used by source-aware deal selection."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


SHOPEE_INFERRED_PREVIOUS_PRICE_SOURCE = "shopee_inferred_from_price_discount_rate"
_CENT = Decimal("0.01")
_HUNDRED = Decimal("100")


def reconstruct_shopee_previous_price(
    current_price: Any,
    discount_pct: Any,
) -> float | None:
    """Infer a reference price from Shopee's current price and discount rate.

    This is an explicit Shopee-only policy.  The provider does not return a
    documented list price, so callers must persist the source marker and must
    not present the result as an API-provided historical price.
    """
    if (
        current_price is None
        or discount_pct is None
        or isinstance(current_price, bool)
        or isinstance(discount_pct, bool)
    ):
        return None

    try:
        current = Decimal(str(current_price).strip())
        discount = Decimal(str(discount_pct).strip())
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return None

    if (
        not current.is_finite()
        or not discount.is_finite()
        or current <= 0
        or discount <= 0
        or discount >= 100
    ):
        return None

    inferred = current / (Decimal("1") - (discount / _HUNDRED))
    inferred = inferred.quantize(_CENT, rounding=ROUND_HALF_UP)
    if inferred <= current:
        return None
    return float(inferred)


def calculate_inferred_savings(
    current_price: Any,
    previous_price: Any,
) -> float | None:
    """Calculate rounded savings for a previously reconstructed price."""
    if (
        current_price is None
        or previous_price is None
        or isinstance(current_price, bool)
        or isinstance(previous_price, bool)
    ):
        return None

    try:
        current = Decimal(str(current_price).strip())
        previous = Decimal(str(previous_price).strip())
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return None

    if not current.is_finite() or not previous.is_finite() or previous <= current:
        return None
    return float((previous - current).quantize(_CENT, rounding=ROUND_HALF_UP))
