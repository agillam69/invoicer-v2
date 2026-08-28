"""Money handling.

All currency values are stored as integer cents. ``Decimal`` is used for every
intermediate calculation and the documented rounding rule is ``ROUND_HALF_UP``
applied once, at the point a value becomes cents.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS_PER_DOLLAR = Decimal(100)
CENT = Decimal(1)


class MoneyError(ValueError):
    """Raised when a value cannot be interpreted as an amount of money."""


def _as_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, bool):
        raise MoneyError("Amount must be a number, not a boolean.")
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    else:
        try:
            decimal_value = Decimal(value.strip())
        except (InvalidOperation, AttributeError) as error:
            raise MoneyError(f"{value!r} is not a valid amount.") from error
    if not decimal_value.is_finite():
        raise MoneyError("Amount must be a finite number.")
    return decimal_value


def round_to_cents(value: Decimal) -> int:
    """Round a cent-denominated ``Decimal`` to whole cents (half up)."""
    if not value.is_finite():
        raise MoneyError("Amount must be a finite number.")
    return int(value.quantize(CENT, rounding=ROUND_HALF_UP))


def to_cents(value: Decimal | int | str) -> int:
    """Convert a dollar amount to integer cents."""
    return round_to_cents(_as_decimal(value) * CENTS_PER_DOLLAR)


def from_cents(cents: int) -> Decimal:
    """Convert integer cents to a two-decimal-place dollar ``Decimal``."""
    return (Decimal(cents) / CENTS_PER_DOLLAR).quantize(Decimal("0.01"))


def parse_money(text: str) -> int:
    """Parse user or import input such as ``"$1,234.50"`` into cents."""
    cleaned = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    if not cleaned:
        raise MoneyError("Amount is required.")
    return to_cents(cleaned)


def format_aud(cents: int, *, include_symbol: bool = True) -> str:
    """Format integer cents for display, e.g. ``$1,234.50``."""
    amount = from_cents(abs(cents))
    rendered = f"{amount:,.2f}"
    sign = "-" if cents < 0 else ""
    return f"{sign}${rendered}" if include_symbol else f"{sign}{rendered}"
