from datetime import date, timedelta
from decimal import Decimal

import pytest

from invoice_manager.application.invoice_service import InvoiceService, InvoiceServiceError
from invoice_manager.domain.statuses import InvoiceStatus
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    AuditRepository,
    ClientRepository,
    InvoiceRepository,
    PaymentRepository,
    SettingRepository,
)


@pytest.fixture
def invoice_deps(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.create_schema()
    session = db.new_session()
    try:
        client_repo = ClientRepository(session)
        client = client_repo.create(name="Acme Corp")
        setting_repo = SettingRepository(session)
        setting_repo.set("next_invoice_number", "5")
        audit = AuditService(AuditRepository(session))
        service = InvoiceService(
            invoice_repo=InvoiceRepository(session),
            client_repo=client_repo,
            payment_repo=PaymentRepository(session),
            setting_repo=setting_repo,
            audit=audit,
            gst_rate=Decimal("0.10"),
            payment_terms_days=7,
        )
        yield service, client, session
        session.commit()
    finally:
        session.close()
        db.engine.dispose()


def test_create_draft(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    assert inv.is_draft is True
    assert inv.number == "DRAFT"
    assert inv.status == InvoiceStatus.DRAFT.value


def test_add_line_recalculates_totals(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Consulting", 2, 10000, taxable=True)
    session.refresh(inv)
    assert inv.subtotal_cents == 20000
    assert inv.gst_cents == 2000
    assert inv.total_cents == 22000


def test_cannot_edit_issued_invoice(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    with pytest.raises(InvoiceServiceError):
        service.add_line(inv, "Extra", 1, 5000)


def test_issue_assigns_number(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    assert inv.number == "INV-0005"
    assert inv.is_draft is False


def test_status_paid_after_payment(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service._payment_repo.create(
        invoice_id=inv.id,
        amount_cents=inv.total_cents,
        date=date.today(),
        method="cash",
    )
    service.recalc(inv)
    assert inv.status == InvoiceStatus.PAID.value


def test_cancel_invoice(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service.cancel(inv, "Client requested")
    assert inv.is_cancelled is True
    assert inv.status == InvoiceStatus.CANCELLED.value


def test_void_invoice(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service.void(inv, "Mistake")
    assert inv.is_void is True
    assert inv.status == InvoiceStatus.VOID.value


def test_due_date_defaults_to_terms(invoice_deps):
    service, client, session = invoice_deps
    today = date.today()
    inv = service.create_draft(client.id, invoice_date=today)
    assert inv.due_date == today + timedelta(days=7)


def test_update_issued_invoice_recalculates_totals(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service.update_invoice(
        inv,
        inv.issue_date,
        inv.due_date,
        None,
        [
            {
                "description": "More work",
                "quantity": 2,
                "unit_price_cents": 10000,
                "discount_cents": 0,
                "taxable": True,
            }
        ],
    )
    assert inv.subtotal_cents == 20000
    assert inv.gst_cents == 2000
    assert inv.total_cents == 22000


def test_update_invoice_with_payments_updates_status(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service._payment_repo.create(
        invoice_id=inv.id,
        amount_cents=11000,
        date=date.today(),
        method="cash",
    )
    service.update_invoice(
        inv,
        inv.issue_date,
        inv.due_date,
        None,
        [
            {
                "description": "Work",
                "quantity": 1,
                "unit_price_cents": 20000,
                "discount_cents": 0,
                "taxable": True,
            }
        ],
    )
    assert inv.status == InvoiceStatus.PART_PAID.value


def test_cannot_update_void_invoice(invoice_deps):
    service, client, session = invoice_deps
    inv = service.create_draft(client.id)
    service.add_line(inv, "Work", 1, 10000)
    service.issue(inv)
    service.void(inv, "Mistake")
    with pytest.raises(InvoiceServiceError):
        service.update_invoice(
            inv,
            inv.issue_date,
            inv.due_date,
            None,
            [
                {
                    "description": "Work",
                    "quantity": 1,
                    "unit_price_cents": 5000,
                    "discount_cents": 0,
                    "taxable": True,
                }
            ],
        )
