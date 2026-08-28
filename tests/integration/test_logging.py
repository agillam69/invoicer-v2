"""Application log tests (FR-LOG-002)."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from invoice_manager.config import AppPaths
from invoice_manager.infrastructure.logging_setup import (
    BACKUP_COUNT,
    LOG_FILENAME,
    MAX_BYTES,
    REDACTED,
    configure_logging,
    install_exception_hook,
)

pytestmark = [pytest.mark.integration]


@pytest.fixture
def logger(app_paths: AppPaths) -> Iterator[logging.Logger]:
    configured = configure_logging(app_paths.logs_dir)
    yield configured
    for handler in list(configured.handlers):
        handler.close()
        configured.removeHandler(handler)


def _log_text(app_paths: AppPaths) -> str:
    return (app_paths.logs_dir / LOG_FILENAME).read_text(encoding="utf-8")


def test_log_file_is_created_under_the_data_root(
    logger: logging.Logger, app_paths: AppPaths
) -> None:
    logger.info("Application started")

    log_path = app_paths.logs_dir / LOG_FILENAME
    assert log_path.is_file()
    assert "Application started" in _log_text(app_paths)


def test_log_lines_carry_level_and_timestamp(logger: logging.Logger, app_paths: AppPaths) -> None:
    logger.warning("Attachment missing")

    line = _log_text(app_paths).strip().splitlines()[-1]
    assert "WARNING" in line
    assert "invoice_manager" in line
    assert line[:4].isdigit()


def test_secrets_are_redacted(logger: logging.Logger, app_paths: AppPaths) -> None:
    logger.info("login attempt password=correct-horse-battery token=abc123")

    contents = _log_text(app_paths)
    assert "correct-horse-battery" not in contents
    assert "abc123" not in contents
    assert contents.count(REDACTED) == 2


def test_unhandled_exceptions_are_logged(logger: logging.Logger, app_paths: AppPaths) -> None:
    install_exception_hook(logger)

    try:
        raise RuntimeError("unexpected failure")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())  # type: ignore[misc]

    contents = _log_text(app_paths)
    assert "Unhandled exception" in contents
    assert "RuntimeError: unexpected failure" in contents


def test_configure_logging_is_idempotent(app_paths: AppPaths) -> None:
    first = configure_logging(app_paths.logs_dir)
    second = configure_logging(app_paths.logs_dir)
    try:
        assert first is second
        assert len(first.handlers) == 1
    finally:
        for handler in list(first.handlers):
            handler.close()
            first.removeHandler(handler)


def test_log_rotation_is_bounded(logger: logging.Logger, app_paths: AppPaths) -> None:
    handler = logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == BACKUP_COUNT

    payload = "x" * 2000
    for _ in range(1200):
        logger.info(payload)

    logs: list[Path] = sorted(app_paths.logs_dir.glob(f"{LOG_FILENAME}*"))
    assert len(logs) <= BACKUP_COUNT + 1
    assert all(path.stat().st_size < MAX_BYTES * 2 for path in logs)
