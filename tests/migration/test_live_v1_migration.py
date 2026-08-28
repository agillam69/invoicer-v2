"""Smoke test migrating the actual v1 data directory into a fresh v2 DB."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from invoice_manager.application.migration_service import MigrationService
from invoice_manager.infrastructure.file_store import FileStore
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.models import (
    Client,
    Invoice,
    LedgerEntry,
    MigrationIssue,
    ServiceItem,
)
from invoice_manager.persistence.repositories import (
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    MigrationIssueRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
)

V1_DATA_DIR = Path(__file__).parents[3].resolve()


@pytest.fixture
def live_source(tmp_path):
    if not (V1_DATA_DIR / "invoices.csv").exists():
        pytest.skip("No live v1 data")
    source = tmp_path / "v1_data"
    source.mkdir()
    for name in ("settings.json", "clients.csv", "service_items.csv", "invoices.csv", "ledger.csv"):
        src = V1_DATA_DIR / name
        if src.exists():
            shutil.copy2(src, source / name)
    (source / "invoices").mkdir(exist_ok=True)
    return source


@pytest.mark.skipif(not (V1_DATA_DIR / "invoices.csv").exists(), reason="No live v1 data")
def test_live_v1_migration(live_source, tmp_path):
    db = Database(tmp_path / "live.sqlite3")
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
        source_dir=live_source,
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
        counts = svc.run()
        session.commit()

        print(f"Migration counts: {counts}")
        issues = session.query(MigrationIssue).all()
        if issues:
            print(f"Migration issues ({len(issues)}):")
            for issue in issues[:20]:
                print(f"  [{issue.severity}] {issue.issue_type}: {issue.message}")

        assert counts["clients"] > 0
        assert counts["services"] > 0
        assert counts["invoices"] > 0
        assert counts["ledger"] >= 0

        assert session.query(Invoice).count() == counts["invoices"]
        assert session.query(Client).count() == counts["clients"]
        assert session.query(ServiceItem).count() == counts["services"]
        assert (
            session.query(LedgerEntry).filter(LedgerEntry.is_deleted.is_(False)).count()
            == counts["ledger"]
        )
    finally:
        session.close()
        db.engine.dispose()
