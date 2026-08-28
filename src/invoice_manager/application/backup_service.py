"""Backup and restore service for the application data directory."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


class BackupServiceError(Exception):
    pass


class BackupService:
    """Create and restore timestamped zip backups of the data tree."""

    MANIFEST_NAME = "backup_manifest.json"

    def __init__(
        self,
        data_dir: Path,
        backup_dir: Path,
        setting_repo: Any | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self._settings = setting_repo
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_backup_dir(self) -> Path:
        if self._settings is None:
            return self.backup_dir
        custom = self._settings.get("backup_folder") or ""
        if custom:
            path = Path(custom)
            path.mkdir(parents=True, exist_ok=True)
            return path
        return self.backup_dir

    def backup(self, backup_dir: Path | None = None) -> Path:
        """Zip the data directory and return the archive path."""
        if not self.data_dir.exists():
            raise BackupServiceError(f"Data directory not found: {self.data_dir}")
        target = Path(backup_dir) if backup_dir else self._resolve_backup_dir()
        target.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = target / f"invoice_manager_backup_{timestamp}.zip"

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / self.MANIFEST_NAME
            manifest = {
                "created_at": datetime.now().isoformat(),
                "version": "2.0",
                "data_dir": str(self.data_dir),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(manifest_path, self.MANIFEST_NAME)
                for path in self.data_dir.rglob("*"):
                    if path.is_file():
                        arcname = f"data/{path.relative_to(self.data_dir)}"
                        zf.write(path, arcname)
        return archive

    def prune(self, target: Path | None = None) -> int:
        """Delete oldest backups beyond the keep count."""
        directory = target or self._resolve_backup_dir()
        keep = 30
        if self._settings is not None:
            try:
                keep = int(self._settings.get("backup_keep") or 30)
            except ValueError:
                keep = 30
        archives = sorted(
            directory.glob("invoice_manager_backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for old in archives[keep:]:
            try:
                old.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def backup_if_due(self) -> bool:
        """Run a scheduled backup if one is due according to settings."""
        if self._settings is None:
            return False
        if self._settings.get("backup_enabled") != "1":
            return False
        try:
            frequency = int(self._settings.get("backup_frequency_hours") or 24)
        except ValueError:
            frequency = 24

        last = self._settings.get("last_backup_timestamp")
        last_time: datetime | None = None
        if last:
            try:
                last_time = datetime.fromisoformat(last)
            except ValueError:
                last_time = None

        now = datetime.now()
        if last_time and (now - last_time).total_seconds() < frequency * 3600:
            return False

        target = self._resolve_backup_dir()
        self.backup(target)
        self.prune(target)
        self._settings.set("last_backup_timestamp", now.isoformat())
        return True

    def backup_on_exit(self) -> bool:
        """Run a backup on application exit if configured."""
        if self._settings is None:
            return False
        if self._settings.get("backup_on_exit") != "1":
            return False
        target = self._resolve_backup_dir()
        self.backup(target)
        self.prune(target)
        return True

    def restore(self, archive: Path) -> None:
        """Restore the data directory from a backup archive."""
        archive = Path(archive)
        if not archive.exists():
            raise BackupServiceError(f"Archive not found: {archive}")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(tmp_path)
            manifest_path = tmp_path / self.MANIFEST_NAME
            if not manifest_path.exists():
                raise BackupServiceError("Backup manifest missing; refusing to restore.")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise BackupServiceError("Invalid backup manifest") from exc
            if manifest.get("version", "").startswith("1"):
                raise BackupServiceError("v1 backups are not supported by this service.")

            # Make a safety backup of the current data before overwriting.
            if self.data_dir.exists():
                safety = self.backup_dir / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(self.data_dir, safety, dirs_exist_ok=True)

            extracted_data = tmp_path / "data"
            if not extracted_data.exists():
                raise BackupServiceError("Backup does not contain a data directory.")
            shutil.copytree(extracted_data, self.data_dir, dirs_exist_ok=True)
