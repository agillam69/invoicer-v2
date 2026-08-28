"""Schema, migration and storage-layout tests (FR-SET-004, FR-DOC-003, FR-PAY-003)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from invoice_manager.config import AppPaths
from invoice_manager.persistence.models import (
    Client,
    Document,
    Invoice,
    InvoiceItem,
    Payment,
    Receipt,
)
from invoice_manager.persistence.schema import (
    current_revision,
    head_revision,
    is_up_to_date,
)

pytestmark = [pytest.mark.integration]

EXPECTED_TABLES = {
    "users",
    "business_profiles",
    "clients",
    "categories",
    "service_items",
    "invoices",
    "invoice_items",
    "payments",
    "receipts",
    "credit_notes",
    "credit_note_items",
    "ledger_entries",
    "documents",
    "audit_events",
    "number_sequences",
    "migration_runs",
    "migration_issues",
}

EXCLUDED_LEGACY_TABLES = {
    "students",
    "courses",
    "enrolments",
    "certificates",
    "certificate_credits",
}


def _client(session: Session) -> Client:
    client = Client(display_name="Town and Country Medical")
    session.add(client)
    session.flush()
    return client


def _issued_invoice(session: Session, *, number: str = "INV-0001") -> Invoice:
    client = _client(session)
    invoice = Invoice(
        canonical_number=number,
        client_id=client.id,
        invoice_date=date(2026, 6, 25),
        due_date=date(2026, 7, 9),
        subtotal_cents=100_00,
        gst_cents=0,
        total_cents=100_00,
        issued_at=datetime(2026, 6, 25, 9, 0),
    )
    invoice.items.append(
        InvoiceItem(
            position=1,
            description="Event medical coverage",
            quantity_decimal=1,
            unit_price_cents=100_00,
            taxable=False,
            subtotal_cents=100_00,
            gst_cents=0,
            total_cents=100_00,
        )
    )
    session.add(invoice)
    session.flush()
    return invoice


def _payment(session: Session, invoice: Invoice) -> Payment:
    payment = Payment(
        invoice_id=invoice.id,
        payment_date=date(2026, 6, 26),
        amount_cents=100_00,
        method="bank_transfer",
    )
    session.add(payment)
    session.flush()
    return payment


def test_migration_creates_every_expected_table(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())

    assert tables >= EXPECTED_TABLES


def test_no_training_tables_are_created(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())

    assert EXCLUDED_LEGACY_TABLES.isdisjoint(tables)


def test_database_is_at_head_revision(engine: Engine, app_paths: AppPaths) -> None:
    url = app_paths.database_url()

    assert current_revision(engine) == head_revision(url)
    assert is_up_to_date(engine, url) is True


def test_sqlite_is_configured_for_safety(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("pragma foreign_keys")).scalar_one() == 1
        assert connection.execute(text("pragma journal_mode")).scalar_one() == "wal"


def test_foreign_keys_are_enforced(session: Session) -> None:
    session.add(Invoice(canonical_number="INV-9999", client_id=4242))
    with pytest.raises(IntegrityError):
        session.flush()


def test_invoice_number_is_unique(session: Session) -> None:
    invoice = _issued_invoice(session)
    session.add(Invoice(canonical_number=invoice.canonical_number, client_id=invoice.client_id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_negative_money_is_rejected_by_the_database(session: Session) -> None:
    invoice = _issued_invoice(session)
    session.add(Payment(invoice_id=invoice.id, amount_cents=-1, payment_date=date(2026, 6, 26)))
    with pytest.raises(IntegrityError):
        session.flush()


def test_issued_invoice_must_carry_a_number(session: Session) -> None:
    client = _client(session)
    session.add(Invoice(client_id=client.id, issued_at=datetime(2026, 6, 25, 9, 0)))
    with pytest.raises(IntegrityError):
        session.flush()


def test_payment_keeps_its_reversal_reason(session: Session) -> None:
    """Reversal is recorded on the payment rather than deleting it (FR-PAY-003)."""
    invoice = _issued_invoice(session)
    payment = _payment(session, invoice)

    payment.reversed_at = datetime(2026, 7, 1, 10, 0)
    payment.reversal_reason = "Bank dishonoured the transfer"
    session.flush()

    stored = session.get(Payment, payment.id)
    assert stored is not None
    assert stored.reversed_at is not None
    assert stored.reversal_reason == "Bank dishonoured the transfer"


def test_reversal_without_a_reason_is_rejected(session: Session) -> None:
    invoice = _issued_invoice(session)
    payment = _payment(session, invoice)

    payment.reversed_at = datetime(2026, 7, 1, 10, 0)
    with pytest.raises(IntegrityError):
        session.flush()


def test_one_receipt_per_payment(session: Session) -> None:
    invoice = _issued_invoice(session)
    payment = _payment(session, invoice)
    session.add(Receipt(canonical_number="RCT-0001", payment_id=payment.id))
    session.flush()

    session.add(Receipt(canonical_number="RCT-0002", payment_id=payment.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_invoice_items_are_removed_with_their_invoice(session: Session) -> None:
    invoice = _issued_invoice(session)
    assert session.execute(text("select count(*) from invoice_items")).scalar_one() == 1

    session.delete(invoice)
    session.flush()

    assert session.execute(text("select count(*) from invoice_items")).scalar_one() == 0


def test_document_records_managed_relative_paths(session: Session) -> None:
    client = _client(session)
    document = Document(
        entity_type="client",
        entity_id=client.id,
        document_type="attachment",
        original_filename="agreement.pdf",
        managed_relative_path="documents/attachments/agreement.pdf",
    )
    session.add(document)
    session.flush()

    stored = session.get(Document, document.id)
    assert stored is not None
    assert stored.managed_relative_path == "documents/attachments/agreement.pdf"
    assert stored.external_path is None


def test_document_needs_a_managed_or_external_location(session: Session) -> None:
    client = _client(session)
    session.add(
        Document(
            entity_type="client",
            entity_id=client.id,
            document_type="attachment",
            original_filename="agreement.pdf",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_managed_storage_layout_is_created(app_paths: AppPaths) -> None:
    for directory in app_paths.all_directories():
        assert directory.is_dir()

    assert app_paths.database_path.parent == app_paths.data_dir
    assert app_paths.backups_dir != app_paths.data_dir
