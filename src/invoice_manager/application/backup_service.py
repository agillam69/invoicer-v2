"""Backup and restore service for the application data directory."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


class BackupServiceError(Exception):
    pass


class BackupService:
    """Create and restore timestamped zip backups of the data tree."""

    MANIFEST_NAME = "backup_manifest.json"

    def __init__(self, data_dir: Path, backup_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self) -> Path:
        """Zip the data directory and return the archive path."""
        if not self.data_dir.exists():
            raise BackupServiceError(f"Data directory not found: {self.data_dir}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = self.backup_dir / f"invoice_manager_backup_{timestamp}.zip"

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
