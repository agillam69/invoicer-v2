"""Derived invoice status (build specification section 16).

Paid, Part Paid and Overdue are always calculated from payments, credits and
the due date. Only Draft, Cancelled and Void may be stored as an override.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from invoice_manager.domain.invoices import balance_cents


class InvoiceStatus(StrEnum):
    DRAFT = "Draft"
    ISSUED = "Issued"
    PART_PAID = "Part Paid"
    PAID = "Paid"
    OVERDUE = "Overdue"
    CREDITED = "Credited"
    CANCELLED = "Cancelled"
    VOID = "Void"


class StatusOverride(StrEnum):
    """The only statuses a user may set directly."""

    DRAFT = "Draft"
    CANCELLED = "Cancelled"
    VOID = "Void"


DERIVED_STATUSES = frozenset(
    {
        InvoiceStatus.ISSUED,
        InvoiceStatus.PART_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.CREDITED,
    }
)


def derive_status(
    *,
    total_cents: int,
    paid_cents: int,
    credited_cents: int,
    due_date: date | None,
    today: date,
    override: StatusOverride | None = None,
) -> InvoiceStatus:
    """Derive the status of a single invoice.

    An overdue balance is reported as Overdue even when part paid, so an unpaid
    remainder past its due date is never presented as merely Part Paid.
    """
    if override is not None:
        return InvoiceStatus(override.value)

    balance = balance_cents(total_cents, paid_cents, credited_cents)
    if balance <= 0:
        return InvoiceStatus.PAID if paid_cents > 0 else InvoiceStatus.CREDITED
    if due_date is not None and due_date < today:
        return InvoiceStatus.OVERDUE
    if paid_cents > 0 or credited_cents > 0:
        return InvoiceStatus.PART_PAID
    return InvoiceStatus.ISSUED
