"""Invoice calculation rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from invoice_manager.domain.money import Money

STANDARD_UNITS = (
    "ea",
    "item",
    "service",
    "hour",
    "day",
    "week",
    "month",
    "session",
    "visit",
    "consultation",
    "report",
    "page",
    "kilometre",
    "package",
    "fixed fee",
)


@dataclass(frozen=True)
class LineItemInput:
    quantity: int = 1
    unit_price_cents: int = 0
    discount_cents: int = 0
    taxable: bool = True


def calculate_discount_cents(value: str, quantity: int, unit_price_cents: int) -> int:
    text = value.strip()
    try:
        if text.endswith("%"):
            percentage = Decimal(text[:-1].strip())
            amount = Decimal(quantity * unit_price_cents) * percentage / 100
        else:
            amount = Decimal(text or "0") * 100
        return max(0, int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except Exception:
        return 0


def calculate_line_total(
    quantity: int,
    unit_price_cents: int,
    discount_cents: int,
    taxable: bool,
    gst_rate: Decimal,
) -> tuple[int, int, int]:
    """Return (subtotal_cents, gst_cents, total_cents) for a line item."""
    gross = quantity * unit_price_cents
    taxable_base = max(0, gross - discount_cents)
    gst = 0
    if taxable and gst_rate > 0:
        gst = int((Decimal(taxable_base) * gst_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    total = taxable_base + gst
    return taxable_base, gst, total


def calculate_invoice_totals(
    lines: list[LineItemInput],
    gst_rate: Decimal,
) -> tuple[int, int, int]:
    """Return (subtotal_cents, gst_cents, total_cents) for a collection of lines."""
    subtotal = 0
    gst = 0
    total = 0
    for line in lines:
        s, g, t = calculate_line_total(
            line.quantity,
            line.unit_price_cents,
            line.discount_cents,
            line.taxable,
            gst_rate,
        )
        subtotal += s
        gst += g
        total += t
    return subtotal, gst, total


def recalculate_invoice(
    invoice_items: list[Any],
    gst_rate: Decimal,
) -> tuple[int, int, int]:
    """Recalculate totals from a list of invoice item-like objects.

    Each item must expose `quantity`, `unit_price_cents`, `discount_cents`,
    `taxable`.  The returned tuple is (subtotal_cents, gst_cents, total_cents).
    """
    lines = [
        LineItemInput(
            quantity=max(1, getattr(item, "quantity", 1)),
            unit_price_cents=getattr(item, "unit_price_cents", 0),
            discount_cents=getattr(item, "discount_cents", 0),
            taxable=getattr(item, "taxable", True),
        )
        for item in invoice_items
    ]
    return calculate_invoice_totals(lines, gst_rate)


@dataclass
class InvoiceTotals:
    subtotal_cents: int = 0
    gst_cents: int = 0
    total_cents: int = 0

    @property
    def subtotal(self) -> Money:
        return Money(cents=self.subtotal_cents)

    @property
    def gst(self) -> Money:
        return Money(cents=self.gst_cents)

    @property
    def total(self) -> Money:
        return Money(cents=self.total_cents)
