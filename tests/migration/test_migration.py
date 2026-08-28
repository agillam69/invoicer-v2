import csv
import json
from datetime import date

import pytest

from invoice_manager.application.migration_service import MigrationService
from invoice_manager.infrastructure.file_store import FileStore
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.models import MigrationIssue
from invoice_manager.persistence.repositories import (
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    MigrationIssueRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
)


@pytest.fixture
def migration_fixtures(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    invoices_dir = source / "invoices"
    invoices_dir.mkdir()

    settings = {
        "business_name": "Test Co",
        "next_invoice_number": 10,
        "payment_terms_days": 14,
    }
    with (source / "settings.json").open("w", encoding="utf-8") as f:
        json.dump(settings, f)

    with (source / "clients.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "contact_name", "phone", "email", "address"])
        w.writeheader()
        w.writerow(
            {"name": "Acme Corp", "contact_name": "", "phone": "", "email": "", "address": ""}
        )
        w.writerow(
            {"name": "Acme Corp", "contact_name": "", "phone": "", "email": "", "address": ""}
        )

    with (source / "service_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["description", "unit_price", "taxable"])
        w.writeheader()
        w.writerow({"description": "Consulting", "unit_price": "100.00", "taxable": "yes"})

    with (source / "invoices.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "invoice_number",
                "invoice_date",
                "due_date",
                "client_name",
                "client_address",
                "notes",
                "subtotal",
                "gst",
                "total",
                "paid",
                "paid_date",
                "payment_note",
                "invoice_status",
                "pdf_path",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "invoice_number": "0001",
                "invoice_date": "2026-06-05",
                "due_date": "2026-07-05",
                "client_name": "Acme Corp",
                "client_address": "",
                "notes": "First invoice",
                "subtotal": "600.00",
                "gst": "0.00",
                "total": "600.00",
                "paid": "yes",
                "paid_date": "2026-06-05",
                "payment_note": "",
                "invoice_status": "paid",
                "pdf_path": "",
            }
        )
        w.writerow(
            {
                "invoice_number": "0002",
                "invoice_date": "2030-06-10",
                "due_date": "",
                "client_name": "Acme Corp",
                "client_address": "",
                "notes": "Second invoice",
                "subtotal": "112.50",
                "gst": "0.00",
                "total": "112.50",
                "paid": "no",
                "paid_date": "",
                "payment_note": "",
                "invoice_status": "unpaid",
                "pdf_path": "",
            }
        )
        w.writerow(
            {
                "invoice_number": "0001-1",
                "invoice_date": "2026-06-05",
                "due_date": "",
                "client_name": "ERROR",
                "client_address": "",
                "notes": "Created In Error",
                "subtotal": "0.00",
                "gst": "0.00",
                "total": "0.00",
                "paid": "yes",
                "paid_date": "2026-06-05",
                "payment_note": "",
                "invoice_status": "paid",
                "pdf_path": "",
            }
        )
        w.writerow(
            {
                "invoice_number": "0003",
                "invoice_date": "2026-06-01",
                "due_date": "",
                "client_name": "Missing Client",
                "client_address": "",
                "notes": "Unknown client",
                "subtotal": "50.00",
                "gst": "0.00",
                "total": "50.00",
                "paid": "no",
                "paid_date": "",
                "payment_note": "",
                "invoice_status": "unpaid",
                "pdf_path": "",
            }
        )

    with (source / "ledger.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "date",
                "type",
                "category",
                "description",
                "amount",
                "reference",
                "notes",
                "deleted",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "id": "1",
                "date": "2026-06-05",
                "type": "out",
                "category": "Supplies",
                "description": "Stationery",
                "amount": "55.00",
                "reference": "",
                "notes": "",
                "deleted": "",
            }
        )
        w.writerow(
            {
                "id": "2",
                "date": "2026-06-05",
                "type": "out",
                "category": "Certification Fee",
                "description": "Auto budget spend",
                "amount": "9.00",
                "reference": "",
                "notes": "",
                "deleted": "",
            }
        )
        w.writerow(
            {
                "id": "3",
                "date": "2026-06-05",
                "type": "out",
                "category": "Travel",
                "description": "Deleted",
                "amount": "20.00",
                "reference": "",
                "notes": "",
                "deleted": "1",
            }
        )

    return source


@pytest.fixture
def migration(migration_fixtures, tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.create_schema()
    session = db.new_session()
    file_store = FileStore(tmp_path / "data")

    settings_repo = SettingRepository(session)
    client_repo = ClientRepository(session)
    service_repo = ServiceItemRepository(session)
    invoice_repo = InvoiceRepository(session)
    payment_repo = PaymentRepository(session)
    ledger_repo = LedgerRepository(session)
    issue_repo = MigrationIssueRepository(session)

    svc = MigrationService(
        source_dir=migration_fixtures,
        setting_repo=settings_repo,
        client_repo=client_repo,
        service_repo=service_repo,
        invoice_repo=invoice_repo,
        payment_repo=payment_repo,
        ledger_repo=ledger_repo,
        issue_repo=issue_repo,
        file_store=file_store,
        payment_terms_days=7,
    )
    try:
        yield svc, session
        session.commit()
    finally:
        session.close()
        db.engine.dispose()


def test_imports_clients_skipping_duplicates(migration):
    svc, _ = migration
    counts = svc.run()
    assert counts["clients"] == 1


def test_imports_service_items(migration):
    svc, session = migration
    svc.run()
    repo = ServiceItemRepository(session)
    assert len(repo.list_active()) == 1
    assert repo.list_active()[0].description == "Consulting"


def test_imports_invoices_and_payments(migration):
    svc, session = migration
    counts = svc.run()
    assert counts["invoices"] == 2
    assert counts["payments"] == 1
    repo = InvoiceRepository(session)
    inv1 = repo.get_by_number("INV-0001")
    inv2 = repo.get_by_number("INV-0002")
    assert inv1 is not None
    assert inv2 is not None
    assert inv1.total_cents == 60000
    assert inv2.total_cents == 11250
    assert len(inv1.payments) == 1
    assert inv1.status == "paid"
    assert inv2.status == "issued"


def test_default_due_date(migration):
    svc, session = migration
    svc.run()
    repo = InvoiceRepository(session)
    inv2 = repo.get_by_number("INV-0002")
    assert inv2.due_date == date(2030, 6, 17)


def test_flags_placeholder_invoice(migration):
    svc, session = migration
    svc.run()
    issues = [
        i for i in session.query(MigrationIssue).all() if i.issue_type == "invalid_invoice_number"
    ]
    assert len(issues) == 1


def test_flags_unknown_client(migration):
    svc, session = migration
    svc.run()
    issues = [i for i in session.query(MigrationIssue).all() if i.issue_type == "unknown_client"]
    assert len(issues) == 1


def test_imports_ledger_skipping_deleted_and_excluded(migration):
    svc, session = migration
    counts = svc.run()
    assert counts["ledger"] == 1
    assert not any(
        entry.category == "Travel" for entry in LedgerRepository(session).list_non_deleted()
    )
    assert not any(
        entry.category == "Certification Fee"
        for entry in LedgerRepository(session).list_non_deleted()
    )


def test_updates_invoice_numbering(migration):
    svc, session = migration
    svc.run()
    next_num = SettingRepository(session).get_int("next_invoice_number", 0)
    assert next_num >= 4
