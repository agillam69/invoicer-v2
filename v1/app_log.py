"""
app_log.py
==========
Application-level logging for Invoice Generator.

Sets up a Python logging.Logger that writes to a rotating plain-text
log file (invoicer.log) in the application data directory.

Usage
-----
    from app_log import setup_logging, get_logger

    # Call once at startup, before any other imports that log:
    setup_logging(data_dir=Path('/path/to/data'))

    # Anywhere else:
    log = get_logger()
    log.info('Something happened')
    log.warning('Watch out')
    log.error('Something went wrong', exc_info=True)

Also installs a global sys.excepthook so unhandled exceptions are
written to the log file (not just to stderr).
"""

import logging
import os
import platform
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FILENAME  = 'invoicer.log'
_MAX_BYTES     = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT  = 10                 # keep up to 10 rotated files
_LOG_FORMAT    = '%(asctime)s  %(levelname)-8s  %(name)-28s  %(message)s'
_DATE_FORMAT   = '%d/%m/%Y %H:%M:%S'
_CONSOLE_FMT   = '%(levelname)-8s %(name)s — %(message)s'

_logger: logging.Logger | None = None
_log_path: Path | None = None
_is_frozen: bool = getattr(sys, 'frozen', False)


def setup_logging(data_dir: Path) -> Path:
    """
    Configure the root 'invoicer' logger.
    Safe to call multiple times — subsequent calls update the file path.
    Returns the path of the log file.
    """
    global _logger, _log_path

    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _log_path = data_dir / _LOG_FILENAME

    first_time = _logger is None
    if first_time:
        _logger = logging.getLogger('invoicer')
        _logger.setLevel(logging.DEBUG)
        _logger.propagate = False

    # Remove any previous file handlers (e.g. after a data-dir change)
    for h in list(_logger.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
            _logger.removeHandler(h)

    fh = RotatingFileHandler(
        _log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    _logger.addHandler(fh)

    # Console handler in development (not in frozen exe)
    if first_time and not _is_frozen:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(_CONSOLE_FMT))
        _logger.addHandler(ch)

    # Install global unhandled-exception hook
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _logger.critical(
            'Unhandled exception — %s: %s',
            exc_type.__name__, exc_value,
            exc_info=(exc_type, exc_value, exc_tb),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    if first_time:
        _log_startup_banner()
    else:
        _logger.info('Log re-pointed to: %s', _log_path)

    return _log_path


def _log_startup_banner():
    """Write a structured startup banner with system info."""
    sep = '=' * 72
    _logger.info(sep)
    _logger.info('Invoice Generator  |  started %s', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    _logger.info('Python  : %s', sys.version.replace('\n', ' '))
    _logger.info('Platform: %s  %s', platform.system(), platform.version())
    _logger.info('Machine : %s  %s', platform.machine(), platform.processor())
    _logger.info('Frozen  : %s', _is_frozen)
    _logger.info('PID     : %s', os.getpid())
    _logger.info('CWD     : %s', os.getcwd())
    _logger.info('Log     : %s', _log_path)
    _logger.info(sep)


def get_logger(name: str = 'invoicer') -> logging.Logger:
    """Return the named child logger (or root invoicer logger if no name)."""
    return logging.getLogger(name if name == 'invoicer' else f'invoicer.{name}')


def log_path() -> Path | None:
    """Return the current log file path, or None if logging not yet set up."""
    return _log_path


def log_event(category: str, action: str, detail: str = '', level: str = 'info'):
    """
    Log a structured business event.

    Parameters
    ----------
    category : str   e.g. 'invoice', 'student', 'course', 'backup'
    action   : str   e.g. 'created', 'deleted', 'exported'
    detail   : str   optional extra context
    level    : str   'debug' | 'info' | 'warning' | 'error'
    """
    logger = get_logger('event')
    msg = f'[{category.upper()}] {action}'
    if detail:
        msg += f'  |  {detail}'
    getattr(logger, level, logger.info)(msg)


def log_summary(label: str, counts: dict):
    """
    Log a structured summary line, e.g. after an import or export.

    Example
    -------
    log_summary('import_csv', {'courses': 3, 'enrolments': 17, 'skipped': 2})
    """
    logger = get_logger('summary')
    parts = '  '.join(f'{k}={v}' for k, v in counts.items())
    logger.info('[SUMMARY] %s  |  %s', label, parts)
