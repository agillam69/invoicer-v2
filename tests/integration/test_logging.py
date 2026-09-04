import logging
import sys
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from invoice_manager.infrastructure.logging_setup import (
    APP_LOG_FILENAME,
    BACKUP_COUNT,
    ERROR_LOG_FILENAME,
    MAX_BYTES,
    REDACTED,
    configure_logging,
    log_user_error,
)


@pytest.fixture
def logger(tmp_path: Path) -> Iterator[logging.Logger]:
    configured = configure_logging(tmp_path)
    yield configured
    for handler in list(configured.handlers):
        handler.close()
        configured.removeHandler(handler)


def _read(tmp_path: Path, filename: str) -> str:
    for handler in logging.getLogger("invoice_manager").handlers:
        handler.flush()
    return (tmp_path / filename).read_text(encoding="utf-8")


def test_rotating_log_is_created(logger: logging.Logger, tmp_path: Path) -> None:
    logger.info("safe event")
    assert "safe event" in _read(tmp_path, APP_LOG_FILENAME)


def test_errors_go_to_error_log_with_location_and_traceback(
    logger: logging.Logger, tmp_path: Path
) -> None:
    try:
        raise ValueError("client name is required")
    except ValueError as exc:
        log_user_error("Creating client failed", exc)

    errors = _read(tmp_path, ERROR_LOG_FILENAME)
    assert "Creating client failed: client name is required" in errors
    assert "ValueError: client name is required" in errors
    assert "test_logging.test_errors_go_to_error_log_with_location_and_traceback" in errors


def test_error_log_excludes_informational_records(logger: logging.Logger, tmp_path: Path) -> None:
    logger.info("Application startup")
    logger.warning("Login failed")
    logger.error("Rendering invoice PDF failed")

    errors = _read(tmp_path, ERROR_LOG_FILENAME)
    assert "Application startup" not in errors
    assert "Login failed" not in errors
    assert "Rendering invoice PDF failed" in errors


def test_secrets_are_redacted_in_both_logs(logger: logging.Logger, tmp_path: Path) -> None:
    logger.error("save failed password=correct-horse-battery token=abc123")

    for filename in (APP_LOG_FILENAME, ERROR_LOG_FILENAME):
        contents = _read(tmp_path, filename)
        assert "correct-horse-battery" not in contents
        assert "abc123" not in contents
        assert contents.count(REDACTED) == 2


def test_unhandled_exceptions_reach_the_error_log(logger: logging.Logger, tmp_path: Path) -> None:
    try:
        raise RuntimeError("unexpected failure")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())  # type: ignore[misc]

    errors = _read(tmp_path, ERROR_LOG_FILENAME)
    assert "Unhandled exception" in errors
    assert "RuntimeError: unexpected failure" in errors


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    first = configure_logging(tmp_path)
    second = configure_logging(tmp_path)
    try:
        assert first is second
        assert len(first.handlers) == 2
    finally:
        for handler in list(first.handlers):
            handler.close()
            first.removeHandler(handler)


def test_log_rotation_is_bounded(logger: logging.Logger, tmp_path: Path) -> None:
    handlers = [handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)]
    assert {handler.maxBytes for handler in handlers} == {MAX_BYTES}
    assert {handler.backupCount for handler in handlers} == {BACKUP_COUNT}

    payload = "x" * 2000
    for _ in range(1200):
        logger.error(payload)

    for filename in (APP_LOG_FILENAME, ERROR_LOG_FILENAME):
        logs = sorted(tmp_path.glob(f"{filename}*"))
        assert len(logs) <= BACKUP_COUNT + 1
        assert all(path.stat().st_size < MAX_BYTES * 2 for path in logs)
