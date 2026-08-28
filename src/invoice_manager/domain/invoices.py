"""Invoice line and total calculations (build specification section 18)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from invoice_manager.domain.money import CENTS_PER_DOLLAR, round_to_cents

HUNDRED = Decimal(100)


class DiscountType(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    PERCENT = "percent"


class InvoiceCalculationError(ValueError):
    """Raised when a line item cannot produce a valid financial result."""


@dataclass(frozen=True, slots=True)
class LineInput:
    """The values a user or importer supplies for one invoice line."""

    quantity: Decimal
    unit_price_cents: int
    discount_type: DiscountType = DiscountType.NONE
    discount_value: Decimal = Decimal(0)
    taxable: bool = True
    gst_rate: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class LineTotals:
    gross_cents: int
    discount_cents: int
    subtotal_cents: int
    gst_cents: int
    total_cents: int


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    subtotal_cents: int
    gst_cents: int
    total_cents: int


def _validated_discount_cents(line: LineInput, gross_cents: int) -> int:
    if line.discount_type is DiscountType.NONE:
        if line.discount_value != 0:
            raise InvoiceCalculationError("A discount value requires a discount type.")
        return 0
    if line.discount_value < 0:
        raise InvoiceCalculationError("Discount cannot be negative.")
    if line.discount_type is DiscountType.PERCENT:
        if line.discount_value > HUNDRED:
            raise InvoiceCalculationError("Percentage discount cannot exceed 100%.")
        discount_cents = round_to_cents(Decimal(gross_cents) * line.discount_value / HUNDRED)
    else:
        discount_cents = round_to_cents(line.discount_value * CENTS_PER_DOLLAR)
    if discount_cents > gross_cents:
        raise InvoiceCalculationError("Discount cannot exceed the line amount.")
    return discount_cents


def calculate_line(line: LineInput) -> LineTotals:
    """Calculate one line, applying the discount before GST."""
    if line.quantity < 0:
        raise InvoiceCalculationError("Quantity cannot be negative.")
    if line.unit_price_cents < 0:
        raise InvoiceCalculationError("Unit price cannot be negative.")
    if line.gst_rate < 0:
        raise InvoiceCalculationError("GST rate cannot be negative.")

    gross_cents = round_to_cents(line.quantity * Decimal(line.unit_price_cents))
    discount_cents = _validated_discount_cents(line, gross_cents)
    subtotal_cents = gross_cents - discount_cents
    gst_cents = round_to_cents(Decimal(subtotal_cents) * line.gst_rate) if line.taxable else 0
    return LineTotals(
        gross_cents=gross_cents,
        discount_cents=discount_cents,
        subtotal_cents=subtotal_cents,
        gst_cents=gst_cents,
        total_cents=subtotal_cents + gst_cents,
    )


def calculate_invoice(lines: Iterable[LineInput]) -> InvoiceTotals:
    """Sum per-line results; never trust supplied calculated columns."""
    line_totals: Sequence[LineTotals] = [calculate_line(line) for line in lines]
    return InvoiceTotals(
        subtotal_cents=sum(item.subtotal_cents for item in line_totals),
        gst_cents=sum(item.gst_cents for item in line_totals),
        total_cents=sum(item.total_cents for item in line_totals),
    )


def balance_cents(total_cents: int, paid_cents: int, credited_cents: int) -> int:
    """Outstanding balance from valid payments and non-void credits."""
    return total_cents - paid_cents - credited_cents
