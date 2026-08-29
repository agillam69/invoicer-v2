"""Tests for logging setup."""

from __future__ import annotations

import logging

from invoice_manager.infrastructure.logging_setup import get_exe_log_path, setup_logging


def test_setup_logging_creates_file(tmp_path):
    log_path = setup_logging(tmp_path)
    assert log_path == tmp_path / "application.log"
    assert log_path.exists()
    logger = logging.getLogger("invoice_manager")
    logger.info("test message")
    content = log_path.read_text(encoding="utf-8")
    assert "test message" in content


def test_get_exe_log_path_not_frozen():
    assert get_exe_log_path() is None


def test_get_exe_log_path_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "InvoiceReceiptManager.exe"
    fake_exe.write_text("")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.argv", [str(fake_exe)], raising=False)
    path = get_exe_log_path()
    assert path == tmp_path / "InvoiceReceiptManager.log"


def test_setup_logging_idempotent(tmp_path):
    setup_logging(tmp_path)
    first_handlers = len(logging.getLogger().handlers)
    setup_logging(tmp_path)
    assert len(logging.getLogger().handlers) == first_handlers
