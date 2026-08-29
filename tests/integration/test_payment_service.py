from datetime import date
from decimal import Decimal

import pytest

from invoice_manager.application.invoice_service import InvoiceService
from invoice_manager.application.ledger_service import LedgerService
from invoice_manager.application.payment_service import PaymentService, PaymentServiceError
from invoice_manager.domain.statuses import InvoiceStatus
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    AuditRepository,
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    PaymentRepository,
    SettingRepository,
)


@pytest.fixture
def payment_deps(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.create_schema()
    session = db.new_session()
    try:
        client_repo = ClientRepository(session)
        client = client_repo.create(name="Acme Corp")
        setting_repo = SettingRepository(session)
        setting_repo.set("next_invoice_number", "1")
        setting_repo.set("next_receipt_number", "1")
        audit = AuditService(AuditRepository(session))
        ledger_service = LedgerService(LedgerRepository(session), audit)
        invoice_service = InvoiceService(
            invoice_repo=InvoiceRepository(session),
            client_repo=client_repo,
            payment_repo=PaymentRepository(session),
            setting_repo=setting_repo,
            audit=audit,
            gst_rate=Decimal("0.10"),
            payment_terms_days=7,
        )
        payment_service = PaymentService(
            payment_repo=PaymentRepository(session),
            invoice_repo=InvoiceRepository(session),
            setting_repo=setting_repo,
            audit=audit,
            ledger_service=ledger_service,
        )
        yield payment_service, invoice_service, client, session
        session.commit()
    finally:
        session.close()
        db.engine.dispose()


def _issue_invoice(invoice_service, client_id, amount_cents=11000):
    inv = invoice_service.create_draft(client_id)
    invoice_service.add_line(inv, "Consulting", 1, amount_cents, taxable=True)
    invoice_service.issue(inv)
    return inv


def test_record_manual_receipt_uses_numbering_and_ledger(payment_deps):
    payment_service, _invoice_service, client, session = payment_deps
    receipt = payment_service.record_manual_receipt(
        client_name=client.name,
        client_id=client.id,
        client_address="1 Main Street",
        amount_cents=12500,
        receipt_date=date.today(),
        method="EFT",
        reference="MANUAL-1",
        description="Consulting deposit",
    )
    session.flush()
    assert receipt.number == "RCT-0001"
    assert receipt.client_name == "Acme Corp"
    assert payment_service.list_manual_receipts() == [receipt]
    entries = payment_service._ledger_service.list_entries()
    assert entries[0].category == "Other Receipt"
    assert entries[0].amount_cents == 12500


def test_record_payment_marks_invoice_paid(payment_deps):
    payment_service, invoice_service, client, session = payment_deps
    inv = _issue_invoice(invoice_service, client.id)
    payment = payment_service.record(
        invoice=inv,
        amount_cents=inv.total_cents,
        payment_date=date.today(),
        method="EFT",
        reference="REF-1",
    )
    assert payment.receipt_number == "RCT-0001"
    assert inv.status == InvoiceStatus.PAID.value


def test_record_payment_creates_ledger_entry(payment_deps):
    payment_service, invoice_service, client, session = payment_deps
    inv = _issue_invoice(invoice_service, client.id)
    payment_service.record(
        invoice=inv,
        amount_cents=inv.total_cents,
        payment_date=date.today(),
        method="Cash",
    )
    entries = (
        ledger_service.list_entries() if (ledger_service := payment_service._ledger_service) else []
    )
    assert len(entries) == 1
    assert entries[0].entry_type == "in"
    assert entries[0].category == "Invoice Payment"
    assert entries[0].amount_cents == inv.total_cents


def test_reverse_payment_updates_invoice_status_and_ledger(payment_deps):
    payment_service, invoice_service, client, session = payment_deps
    inv = _issue_invoice(invoice_service, client.id)
    payment = payment_service.record(
        invoice=inv,
        amount_cents=inv.total_cents,
        payment_date=date.today(),
        method="Cheque",
    )
    assert inv.status == InvoiceStatus.PAID.value

    payment_service.reverse(payment, "Refund issued")
    assert payment.is_reversed is True
    assert inv.status != InvoiceStatus.PAID.value

    entries = payment_service._ledger_service.list_entries()
    assert len(entries) == 2
    assert entries[1].entry_type == "out"
    assert entries[1].category == "Invoice Payment Reversal"
    assert entries[1].amount_cents == payment.amount_cents


def test_record_partial_payment(payment_deps):
    payment_service, invoice_service, client, session = payment_deps
    inv = _issue_invoice(invoice_service, client.id)
    payment_service.record(
        invoice=inv,
        amount_cents=inv.total_cents // 2,
        payment_date=date.today(),
        method="Card",
    )
    assert inv.status == InvoiceStatus.PART_PAID.value


def test_cannot_pay_draft_invoice(payment_deps):
    payment_service, invoice_service, client, session = payment_deps
    inv = invoice_service.create_draft(client.id)
    with pytest.raises(PaymentServiceError):
        payment_service.record(
            invoice=inv,
            amount_cents=1000,
            payment_date=date.today(),
            method="Cash",
        )
