"""Exact AUD money helpers.

Money is stored as integer cents. Decimal values are rounded once, using
ROUND_HALF_UP, at the cent boundary; binary floats are rejected.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from numbers import Real

CENT = Decimal("0.01")


class MoneyError(ValueError):
    """Raised when a money value is invalid."""


def _decimal(value: Decimal | str | int) -> Decimal:
    if isinstance(value, float) or isinstance(value, Real) and not isinstance(value, int):
        raise MoneyError("binary floating point is not accepted for money")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError("invalid monetary amount") from exc


def dollars_to_cents(value: Decimal | str | int) -> int:
    if isinstance(value, str):
        value = value.replace(",", "")
    amount = _decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    cents = int(amount * 100)
    if cents < 0:
        raise MoneyError("money cannot be negative")
    return cents


def cents_to_decimal(cents: int) -> Decimal:
    if not isinstance(cents, int) or isinstance(cents, bool) or cents < 0:
        raise MoneyError("cents must be a non-negative integer")
    return (Decimal(cents) / 100).quantize(CENT)


def format_aud(cents: int) -> str:
    return f"A${cents_to_decimal(cents):,.2f}"


def parse_aud(value: str | Decimal | int) -> int:
    if isinstance(value, str):
        value = value.strip().replace("A$", "").replace("$", "").replace(",", "")
    return dollars_to_cents(value)


def percentage_amount(base_cents: int, rate: Decimal | str | int) -> int:
    if base_cents < 0:
        raise MoneyError("base cannot be negative")
    rate_decimal = _decimal(rate)
    if rate_decimal < 0:
        raise MoneyError("rate cannot be negative")
    return int((Decimal(base_cents) * rate_decimal / 100).quantize(Decimal("1"), ROUND_HALF_UP))


def multiply_quantity(quantity: Decimal | str | int, unit_price_cents: int) -> int:
    q = _decimal(quantity)
    if q < 0 or unit_price_cents < 0:
        raise MoneyError("quantity and price cannot be negative")
    return int((q * Decimal(unit_price_cents)).quantize(Decimal("1"), ROUND_HALF_UP))
