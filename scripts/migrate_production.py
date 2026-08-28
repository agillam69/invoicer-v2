"""Migrate the live v1 CSV data into the production v2 database."""
from __future__ import annotations

import sys
from pathlib import Path

from invoice_manager.application.auth_service import AuthService
from invoice_manager.application.backup_service import BackupService, BackupServiceError
from invoice_manager.application.migration_service import MigrationService
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.infrastructure.file_store import FileStore
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    AuditRepository,
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    MigrationIssueRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
    UserRepository,
)

SOURCE_DIR = Path("C:/Users/agill/OneDrive/Invoicer")


def main() -> int:
    if not SOURCE_DIR.exists():
        print(f"Source directory not found: {SOURCE_DIR}", file=sys.stderr)
        return 1

    config = AppConfig()
    data_dir = config.get_data_directory()
    backup_dir = config.get_backup_directory()

    # Safety backup of any existing production data.
    if data_dir.exists() and any(data_dir.iterdir()):
        print(f"Existing data found at {data_dir}; creating safety backup...")
        try:
            BackupService(data_dir, backup_dir).backup()
        except BackupServiceError as exc:
            print(f"Safety backup failed: {exc}", file=sys.stderr)
            return 1

    db = Database(config.db_path())
    db.create_schema()
    session = db.new_session()
    try:
        # Ensure the default admin user exists.
        auth = AuthService(UserRepository(session))
        auth.ensure_default_admin()
        session.commit()

        file_store = FileStore(data_dir)
        service = MigrationService(
            source_dir=SOURCE_DIR,
            setting_repo=SettingRepository(session),
            client_repo=ClientRepository(session),
            service_repo=ServiceItemRepository(session),
            invoice_repo=InvoiceRepository(session),
            payment_repo=PaymentRepository(session),
            ledger_repo=LedgerRepository(session),
            issue_repo=MigrationIssueRepository(session),
            file_store=file_store,
            payment_terms_days=7,
        )
        counts = service.run()
        session.commit()
        print("Migration complete:", counts)

        issues = MigrationIssueRepository(session).list_all()
        if issues:
            print("\nIssues flagged:")
            for issue in issues:
                print(f"  [{issue.severity}] {issue.issue_type}: {issue.message}")
        else:
            print("No issues flagged.")
    finally:
        session.close()
        db.engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
