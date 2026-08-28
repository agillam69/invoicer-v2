"""Application paths and runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_FOLDER_NAME = "InvoiceReceiptManager"
DATA_ROOT_ENV_VAR = "INVOICE_MANAGER_DATA_ROOT"
DATABASE_FILENAME = "business.sqlite3"


def default_data_root() -> Path:
    """Resolve the user-data root, keeping it separate from program files."""
    override = os.environ.get(DATA_ROOT_ENV_VAR)
    if override:
        return Path(override).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home()
    return base / APP_FOLDER_NAME


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Every directory the application writes to."""

    root: Path

    @classmethod
    def resolve(cls, root: Path | None = None) -> AppPaths:
        return cls(root=(root or default_data_root()).expanduser())

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

    @property
    def documents_dir(self) -> Path:
        return self.root / "documents"

    @property
    def attachments_dir(self) -> Path:
        return self.documents_dir / "attachments"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def document_type_dir(self, document_type: str, year: int) -> Path:
        """Managed storage for a generated document, e.g. ``invoices/2026``."""
        return self.documents_dir / document_type / str(year)

    def all_directories(self) -> tuple[Path, ...]:
        return (
            self.data_dir,
            self.documents_dir / "invoices",
            self.documents_dir / "receipts",
            self.documents_dir / "credit-notes",
            self.attachments_dir,
            self.exports_dir,
            self.backups_dir,
            self.logs_dir,
        )

    def ensure_directories(self) -> None:
        for directory in self.all_directories():
            directory.mkdir(parents=True, exist_ok=True)

    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_path}"


def is_onedrive_path(path: Path) -> bool:
    """Detect a OneDrive-backed location; the live database should be local."""
    parts = {part.lower() for part in path.parts}
    return any(part.startswith("onedrive") for part in parts)
