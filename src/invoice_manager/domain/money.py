"""Money handling: all stored amounts are integer cents.

Decimal is used only during intermediate calculations; final values are rounded
to cents using ROUND_HALF_UP and stored as int.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

Numeric = int | float | str | Decimal


def to_cents(value: Numeric | None) -> int:
    """Convert a numeric/string/Decimal value to integer cents.

    Strings may contain a currency symbol and commas.  Returns 0 for empty/None.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return int(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
    s = str(value).replace(",", "").replace("$", "").strip()
    if s == "":
        return 0
    d = Decimal(s)
    return int(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def from_cents(cents: int) -> Decimal:
    """Return a Decimal dollars value from integer cents."""
    return Decimal(cents) / 100


def format_money(cents: int, symbol: str = "$", decimals: bool = True) -> str:
    """Format cents as a currency string, e.g. '$12.34'."""
    value = from_cents(cents)
    if decimals:
        return f"{symbol}{value:.2f}"
    return f"{symbol}{value:.0f}"


class Money:
    """Immutable money value stored as integer cents."""

    def __init__(self, value: Numeric | None = None, cents: int | None = None) -> None:
        if cents is not None:
            self._cents = int(cents)
        else:
            self._cents = to_cents(value)

    @property
    def cents(self) -> int:
        return self._cents

    def to_decimal(self) -> Decimal:
        return from_cents(self._cents)

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(cents=self._cents + other._cents)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(cents=self._cents - other._cents)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._cents == other._cents

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._cents < other._cents

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._cents <= other._cents

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._cents > other._cents

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._cents >= other._cents

    def __repr__(self) -> str:
        return f"Money({self.to_decimal():.2f})"

    def __str__(self) -> str:
        return format_money(self._cents)

    @staticmethod
    def zero() -> Money:
        return Money(cents=0)
