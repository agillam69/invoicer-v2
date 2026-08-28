"""Invoice lifecycle status rules."""

from __future__ import annotations

from datetime import date
from enum import StrEnum


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PART_PAID = "part_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CREDITED = "credited"
    CANCELLED = "cancelled"
    VOID = "void"


def derive_invoice_status(
    invoice_total_cents: int,
    balance_cents: int,
    due_date: date | str | None,
    is_cancelled: bool = False,
    is_void: bool = False,
    today: date | None = None,
) -> InvoiceStatus:
    """Derive the display status from financial facts only.

    The order of precedence is: void > cancelled > paid/credited > part paid >
    overdue > issued > draft.
    """
    if today is None:
        today = date.today()
    if is_void:
        return InvoiceStatus.VOID
    if is_cancelled:
        return InvoiceStatus.CANCELLED
    if balance_cents <= 0:
        if invoice_total_cents <= 0:
            return InvoiceStatus.CANCELLED
        return InvoiceStatus.PAID
    # balance > 0
    if balance_cents < invoice_total_cents:
        return InvoiceStatus.PART_PAID
    due = _to_date(due_date)
    if due is not None and due < today:
        return InvoiceStatus.OVERDUE
    return InvoiceStatus.ISSUED


def _to_date(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    from invoice_manager.domain.validation import parse_date

    parsed = parse_date(str(value))
    return parsed
