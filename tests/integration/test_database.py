from sqlalchemy import text

from invoice_manager.persistence.database import Database


def test_schema_creation(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.create_schema()
    session = db.new_session()
    try:
        result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        names = {row[0] for row in result}
        expected = {
            "users",
            "settings",
            "clients",
            "service_items",
            "invoices",
            "invoice_items",
            "payments",
            "credit_notes",
            "ledger_entries",
            "audit_logs",
            "documents",
            "migration_issues",
        }
        assert expected.issubset(names)
    finally:
        session.close()
        db.engine.dispose()
