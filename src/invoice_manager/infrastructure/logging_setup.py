"""Rotating application log and a global exception hook."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER_NAME = "invoice_manager"
LOG_FILENAME = "app.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5

_SECRET_PATTERN = re.compile(
    r"(password|password_hash|secret|token|argon2[^\s\"']*)(\s*[=:]\s*)(\S+)",
    re.IGNORECASE,
)
REDACTED = "***"


class SecretRedactingFilter(logging.Filter):
    """Keep credentials out of the log file and diagnostic bundles."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_PATTERN.sub(rf"\1\2{REDACTED}", str(record.getMessage()))
        record.args = None
        return True


def configure_logging(logs_dir: Path, *, level: int = logging.INFO) -> logging.Logger:
    """Configure the rotating app log; safe to call more than once."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    log_path = logs_dir / LOG_FILENAME
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path):
            return logger

    handler = RotatingFileHandler(
        log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SecretRedactingFilter())
    logger.addHandler(handler)
    return logger


def install_exception_hook(logger: logging.Logger) -> None:
    """Log otherwise unhandled exceptions instead of failing silently."""

    def hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = hook
