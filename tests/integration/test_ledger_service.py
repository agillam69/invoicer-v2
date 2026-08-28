from datetime import date

import pytest

from invoice_manager.application.ledger_service import LedgerService, LedgerServiceError
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import AuditRepository, LedgerRepository


@pytest.fixture
def ledger_svc(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.create_schema()
    session = db.new_session()
    try:
        audit = AuditService(AuditRepository(session))
        service = LedgerService(LedgerRepository(session), audit)
        yield service, session
        session.commit()
    finally:
        session.close()
        db.engine.dispose()


def test_add_expense(ledger_svc):
    service, session = ledger_svc
    entry = service.add_entry(
        entry_date=date.today(),
        entry_type="out",
        category="Supplies",
        description="Stationery",
        amount_cents=5500,
    )
    assert entry.category == "Supplies"
    assert entry.amount_cents == 5500
    assert len(service.list_entries()) == 1


def test_add_income(ledger_svc):
    service, session = ledger_svc
    entry = service.add_entry(
        entry_date=date.today(),
        entry_type="in",
        category="Other Income",
        description="Refund",
        amount_cents=1000,
    )
    assert entry.entry_type == "in"


def test_invalid_entry_type(ledger_svc):
    service, session = ledger_svc
    with pytest.raises(LedgerServiceError):
        service.add_entry(date.today(), "up", "Bad", "test", 100)


def test_zero_amount_rejected(ledger_svc):
    service, session = ledger_svc
    with pytest.raises(LedgerServiceError):
        service.add_entry(date.today(), "out", "Bad", "test", 0)


def test_update_entry(ledger_svc):
    service, session = ledger_svc
    entry = service.add_entry(
        entry_date=date.today(),
        entry_type="out",
        category="Supplies",
        description="Stationery",
        amount_cents=5500,
    )
    service.update_entry(
        entry=entry,
        entry_date=date.today(),
        entry_type="out",
        category="Office",
        description="Pens",
        amount_cents=1200,
        reference="PO-1",
        notes="updated",
    )
    assert entry.category == "Office"
    assert entry.amount_cents == 1200
    assert entry.reference == "PO-1"


def test_delete_entry(ledger_svc):
    service, session = ledger_svc
    entry = service.add_entry(
        entry_date=date.today(),
        entry_type="out",
        category="Supplies",
        description="Stationery",
        amount_cents=5500,
    )
    service.delete_entry(entry, "Entered twice")
    assert entry.is_deleted is True
    assert len(service.list_entries()) == 0
