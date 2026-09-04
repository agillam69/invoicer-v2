from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER_NAME = "invoice_manager"
APP_LOG_FILENAME = "app.log"
ERROR_LOG_FILENAME = "error.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5

APP_FORMAT = "%(asctime)s %(levelname)s %(message)s"
ERROR_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s %(processName)s/%(threadName)s "
    "%(module)s.%(funcName)s:%(lineno)d %(message)s"
)

_SECRET_PATTERN = re.compile(
    r"(password|password_hash|secret|token|argon2[^\s\"']*)(\s*[=:]\s*)(\S+)",
    re.IGNORECASE,
)
REDACTED = "***"


class SecretRedactingFilter(logging.Filter):
    """Keep credentials out of the log files and diagnostic bundles."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_PATTERN.sub(rf"\1\2{REDACTED}", str(record.getMessage()))
        record.args = None
        return True


def log_user_error(context: str, exc: BaseException) -> None:
    """Record a failure that was surfaced to the user, with a traceback."""
    logging.getLogger(LOGGER_NAME).error("%s: %s", context, exc, exc_info=exc, stacklevel=2)


def _rotating_handler(path: Path, level: int, fmt: str) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(SecretRedactingFilter())
    return handler


def _has_handler_for(logger: logging.Logger, path: Path) -> bool:
    return any(
        isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(path)
        for handler in logger.handlers
    )


def configure_logging(log_dir: Path, *, level: int = logging.INFO) -> logging.Logger:
    """Configure the app and error logs; safe to call more than once."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    app_log = log_dir / APP_LOG_FILENAME
    if not _has_handler_for(logger, app_log):
        logger.addHandler(_rotating_handler(app_log, level, APP_FORMAT))

    error_log = log_dir / ERROR_LOG_FILENAME
    if not _has_handler_for(logger, error_log):
        logger.addHandler(_rotating_handler(error_log, logging.ERROR, ERROR_FORMAT))

    def handle_exception(
        exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
        else:
            logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = handle_exception
    return logger
