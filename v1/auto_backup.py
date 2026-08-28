"""
auto_backup.py
==============
Silent scheduled backup engine for Invoice Generator.

Runs entirely in a daemon thread — never touches the Tkinter mainloop.
All public methods are thread-safe relative to the main thread.

Backup strategy
---------------
- Backups are written as timestamped zips:
      <backup_dir>/invoicer_backup_YYYYMMDD_HHMMSS.zip
- Old backups are pruned so only the N most-recent are kept.
- Failures are logged but never raised (silent by design).

Usage (from InvoiceApp)
-----------------------
    self._backup_mgr = AutoBackupManager(ds, settings_fn)
    self._backup_mgr.start()                 # begin scheduling
    self._backup_mgr.run_now(on_exit=True)   # call from on-close handler
    self._backup_mgr.stop()                  # graceful shutdown
"""

import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

_log = logging.getLogger(__name__)

_INTERVALS = {
    'hourly':    1,
    'every2h':   2,
    'every4h':   4,
    'every6h':   6,
    'every12h': 12,
    'daily':    24,
}


class AutoBackupManager:
    """Manages silent, scheduled backups of the DataStore."""

    def __init__(self, ds, settings_fn):
        """
        ds          : DataStore instance
        settings_fn : callable() -> settings dict  (called fresh each time)
        """
        self.ds = ds
        self.settings_fn = settings_fn
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._stopped = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self):
        """Begin the scheduling loop."""
        self._stopped = False
        self._schedule_next()

    def stop(self):
        """Cancel any pending timer (does NOT run the backup)."""
        self._stopped = True
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def run_now(self, on_exit: bool = False):
        """
        Run a backup immediately in the calling thread.
        Pass on_exit=True to respect the 'backup_on_exit' setting.
        """
        settings = self.settings_fn()
        if not settings.get('auto_backup_enabled', False):
            return
        if on_exit and not settings.get('backup_on_exit', True):
            return
        self._do_backup(settings)

    def apply_new_settings(self):
        """
        Call after settings are saved so the next timer fires at the
        correct interval.  Cancels the current timer and reschedules.
        """
        self.stop()
        self._stopped = False
        self._schedule_next()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _schedule_next(self):
        settings = self.settings_fn()
        if not settings.get('auto_backup_enabled', False):
            return
        freq = settings.get('backup_frequency', 'daily')
        interval_h = _INTERVALS.get(freq, 24)
        delay_s = interval_h * 3600
        with self._lock:
            if self._stopped:
                return
            self._timer = threading.Timer(delay_s, self._fire)
            self._timer.daemon = True
            self._timer.start()
        _log.debug('Auto-backup scheduled in %sh (freq=%s)', interval_h, freq)

    def _fire(self):
        """Timer callback — runs backup then reschedules."""
        if self._stopped:
            return
        settings = self.settings_fn()
        self._do_backup(settings)
        self._schedule_next()

    def _do_backup(self, settings: dict):
        """Write the zip and prune old copies.  Never raises."""
        try:
            backup_dir = Path(settings.get('backup_dir', '').strip()
                              or self.ds.data_dir / 'backups')
            backup_dir.mkdir(parents=True, exist_ok=True)

            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_path = backup_dir / f'invoicer_backup_{stamp}.zip'

            self.ds.export_all(zip_path)
            _log.info('Auto-backup written: %s', zip_path)

            self._prune(backup_dir, settings)
        except Exception as exc:
            _log.error('Auto-backup failed: %s', exc, exc_info=True)

    def _prune(self, backup_dir: Path, settings: dict):
        """Delete oldest backups beyond the keep-last-N limit."""
        try:
            keep = int(settings.get('backup_keep', 10))
            keep = max(1, keep)
        except (ValueError, TypeError):
            keep = 10
        try:
            zips = sorted(backup_dir.glob('invoicer_backup_*.zip'),
                          key=lambda p: p.stat().st_mtime)
            for old in zips[:-keep]:
                old.unlink(missing_ok=True)
                _log.info('Auto-backup pruned old copy: %s', old.name)
        except Exception as exc:
            _log.warning('Auto-backup prune failed: %s', exc)

    # ------------------------------------------------------------------
    # Introspection (for the status line in Settings)
    # ------------------------------------------------------------------
    def next_backup_eta(self) -> str:
        """Return a human-readable ETA string, or '' if not scheduled."""
        with self._lock:
            t = self._timer
        if t is None or self._stopped:
            return ''
        settings = self.settings_fn()
        freq = settings.get('backup_frequency', 'daily')
        interval_h = _INTERVALS.get(freq, 24)
        eta = datetime.now() + timedelta(hours=interval_h)
        return eta.strftime('%d/%m/%Y %H:%M')

    @staticmethod
    def list_backups(backup_dir: Path) -> list[dict]:
        """Return list of dicts describing existing backup zips, newest first."""
        result = []
        try:
            for p in sorted(backup_dir.glob('invoicer_backup_*.zip'),
                            key=lambda x: x.stat().st_mtime, reverse=True):
                stat = p.stat()
                result.append({
                    'name':     p.name,
                    'path':     str(p),
                    'size_kb':  round(stat.st_size / 1024, 1),
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
                })
        except Exception:
            pass
        return result
