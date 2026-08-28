"""Derived status tests (FR-INV-007, FR-INV-012, FR-PAY-003)."""

from __future__ import annotations

from datetime import date

import pytest

from invoice_manager.domain.credits import (
    CreditError,
    CreditRecord,
    valid_credit_total,
    validate_credit_amount,
)
from invoice_manager.domain.payments import (
    PaymentError,
    PaymentRecord,
    is_overpayment,
    valid_payment_total,
    validate_payment_amount,
)
from invoice_manager.domain.statuses import InvoiceStatus, StatusOverride, derive_status

TODAY = date(2026, 7, 15)
TOTAL = 60000

pytestmark = [pytest.mark.domain]


def status(
    *,
    paid: int = 0,
    credited: int = 0,
    total: int = TOTAL,
    due_date: date | None = date(2026, 7, 29),
    override: StatusOverride | None = None,
) -> InvoiceStatus:
    return derive_status(
        total_cents=total,
        paid_cents=paid,
        credited_cents=credited,
        due_date=due_date,
        today=TODAY,
        override=override,
    )


def test_issued_invoice_before_due_date() -> None:
    assert status() is InvoiceStatus.ISSUED


def test_part_paid_when_some_payment_recorded() -> None:
    assert status(paid=20000) is InvoiceStatus.PART_PAID


def test_paid_when_payments_clear_the_balance() -> None:
    assert status(paid=TOTAL) is InvoiceStatus.PAID


def test_credited_when_credits_clear_the_balance() -> None:
    assert status(credited=TOTAL) is InvoiceStatus.CREDITED


def test_paid_wins_when_payments_and_credits_clear_the_balance() -> None:
    assert status(paid=30000, credited=30000) is InvoiceStatus.PAID


def test_overdue_when_due_date_has_passed() -> None:
    assert status(due_date=date(2026, 7, 14)) is InvoiceStatus.OVERDUE


def test_due_today_is_not_yet_overdue() -> None:
    assert status(due_date=TODAY) is InvoiceStatus.ISSUED


def test_overdue_reported_ahead_of_part_paid() -> None:
    assert status(paid=20000, due_date=date(2026, 6, 30)) is InvoiceStatus.OVERDUE


def test_paid_invoice_past_due_is_not_overdue() -> None:
    assert status(paid=TOTAL, due_date=date(2026, 6, 30)) is InvoiceStatus.PAID


def test_invoice_without_due_date_is_never_overdue() -> None:
    assert status(due_date=None) is InvoiceStatus.ISSUED


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        (StatusOverride.DRAFT, InvoiceStatus.DRAFT),
        (StatusOverride.CANCELLED, InvoiceStatus.CANCELLED),
        (StatusOverride.VOID, InvoiceStatus.VOID),
    ],
)
def test_stored_overrides_take_precedence(
    override: StatusOverride, expected: InvoiceStatus
) -> None:
    assert status(paid=TOTAL, override=override) is expected


def test_zero_total_invoice_without_payment_is_not_marked_paid() -> None:
    """A $0 invoice with no payment is Credited for review, never silently Paid."""
    assert status(total=0) is InvoiceStatus.CREDITED


def test_reversed_payments_are_excluded_and_restore_status() -> None:
    payments = [
        PaymentRecord(amount_cents=TOTAL, payment_date=date(2026, 7, 1)),
        PaymentRecord(amount_cents=TOTAL, payment_date=date(2026, 7, 2), reversed_=True),
    ]
    assert valid_payment_total(payments) == TOTAL
    assert status(paid=valid_payment_total(payments)) is InvoiceStatus.PAID

    reversed_only = [PaymentRecord(amount_cents=TOTAL, reversed_=True)]
    assert valid_payment_total(reversed_only) == 0
    assert status(paid=valid_payment_total(reversed_only)) is InvoiceStatus.ISSUED


def test_void_credits_are_excluded() -> None:
    credits = [CreditRecord(total_cents=10000), CreditRecord(total_cents=5000, void=True)]
    assert valid_credit_total(credits) == 10000


@pytest.mark.parametrize("amount", [0, -1])
def test_payment_amount_must_be_positive(amount: int) -> None:
    with pytest.raises(PaymentError):
        validate_payment_amount(amount)


def test_overpayment_is_detected() -> None:
    assert is_overpayment(60001, TOTAL) is True
    assert is_overpayment(TOTAL, TOTAL) is False


def test_credit_cannot_exceed_remaining_amount() -> None:
    validate_credit_amount(10000, 10000)
    with pytest.raises(CreditError):
        validate_credit_amount(10001, 10000)
    with pytest.raises(CreditError):
        validate_credit_amount(0, 10000)
