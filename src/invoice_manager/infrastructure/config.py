"""Application configuration and storage layout."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class AppConfig:
    """Manages the storage layout and runtime configuration file."""

    APP_DIR_NAME = "InvoiceReceiptManager"
    CONFIG_FILE = "config.json"

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = self._default_base_dir()
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / self.CONFIG_FILE
        self.data_dir: Path = self.base_dir / "data"
        self.documents_dir: Path = self.base_dir / "documents"
        self.exports_dir: Path = self.base_dir / "exports"
        self.backups_dir: Path = self.base_dir / "backups"
        self.logs_dir: Path = self.base_dir / "logs"
        self._ensure_dirs()

    @classmethod
    def _default_base_dir(cls) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / cls.APP_DIR_NAME
        return Path.home() / ".invoice_receipt_manager"

    def _ensure_dirs(self) -> None:
        for directory in (
            self.base_dir,
            self.data_dir,
            self.documents_dir,
            self.exports_dir,
            self.backups_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def db_path(self) -> Path:
        return self.data_dir / "business.sqlite3"

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def save(self, values: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(values, f, indent=4)

    def get_data_directory(self) -> Path:
        cfg = self.load()
        custom = cfg.get("data_dir", "")
        if custom:
            path = Path(custom)
            path.mkdir(parents=True, exist_ok=True)
            return path
        return self.base_dir

    def get_backup_directory(self) -> Path:
        return self.backups_dir

    def get_documents_directory(self) -> Path:
        return self.documents_dir

    def get_exports_directory(self) -> Path:
        return self.exports_dir

    def get_logs_directory(self) -> Path:
        return self.logs_dir

    def set_data_directory(self, path: Path) -> None:
        cfg = self.load()
        cfg["data_dir"] = str(Path(path))
        self.save(cfg)
