from datetime import date, timedelta

from invoice_manager.domain.statuses import InvoiceStatus, derive_invoice_status


def test_paid_when_balance_zero():
    assert (
        derive_invoice_status(invoice_total_cents=1000, balance_cents=0, due_date=None)
        == InvoiceStatus.PAID
    )


def test_part_paid():
    assert (
        derive_invoice_status(invoice_total_cents=1000, balance_cents=400, due_date=None)
        == InvoiceStatus.PART_PAID
    )


def test_overdue():
    past = date.today() - timedelta(days=1)
    assert (
        derive_invoice_status(invoice_total_cents=1000, balance_cents=1000, due_date=past)
        == InvoiceStatus.OVERDUE
    )


def test_issued_not_overdue():
    future = date.today() + timedelta(days=1)
    assert (
        derive_invoice_status(invoice_total_cents=1000, balance_cents=1000, due_date=future)
        == InvoiceStatus.ISSUED
    )


def test_void_takes_precedence():
    assert (
        derive_invoice_status(
            invoice_total_cents=1000,
            balance_cents=0,
            due_date=None,
            is_void=True,
        )
        == InvoiceStatus.VOID
    )


def test_cancelled_takes_precedence():
    assert (
        derive_invoice_status(
            invoice_total_cents=1000,
            balance_cents=500,
            due_date=None,
            is_cancelled=True,
        )
        == InvoiceStatus.CANCELLED
    )
