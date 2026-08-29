"""Tests for the full data export service."""

from __future__ import annotations

import zipfile
from pathlib import Path

from invoice_manager.application.export_service import DataExportService
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import ClientRepository


def test_export_all_creates_zip_with_manifest(tmp_path: Path) -> None:
    config = AppConfig(tmp_path)
    (config.data_dir / "business.sqlite3").write_text("fake db", encoding="utf-8")
    (config.documents_dir / "invoices" / "INV-0001.pdf").mkdir(parents=True)
    (config.documents_dir / "invoices" / "INV-0001.pdf" / "file").write_text("pdf", encoding="utf-8")
    (config.logs_dir / "application.log").write_text("log", encoding="utf-8")

    service = DataExportService(config)
    archive = service.export_all()

    assert archive.exists()
    with zipfile.ZipFile(archive, "r") as zf:
        names = zf.namelist()
        assert "export_manifest.json" in names
        assert any("data/" in n for n in names)
        assert any("documents/" in n for n in names)
        assert any("logs/" in n for n in names)


def test_export_all_includes_database_csv_when_session_is_supplied(tmp_path: Path) -> None:
    config = AppConfig(tmp_path)
    database = Database(config.db_path())
    database.create_schema()
    session = database.new_session()
    try:
        ClientRepository(session).create(name="Acme")
        session.commit()
        archive = DataExportService(config, session).export_all()
        with zipfile.ZipFile(archive, "r") as zf:
            assert "database_csv/clients.csv" in zf.namelist()
            assert "Acme" in zf.read("database_csv/clients.csv").decode("utf-8")
    finally:
        session.close()
        database.engine.dispose()


def test_export_all_allows_custom_target(tmp_path: Path) -> None:
    config = AppConfig(tmp_path)
    (config.data_dir / "business.sqlite3").write_text("fake db", encoding="utf-8")
    target = tmp_path / "custom_export.zip"

    service = DataExportService(config)
    archive = service.export_all(target)

    assert archive == target
    assert target.exists()
