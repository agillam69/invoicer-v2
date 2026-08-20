from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data: Path
    database: Path
    documents: Path
    exports: Path
    backups: Path
    logs: Path

    @classmethod
    def resolve(cls, root: Path | None = None) -> AppPaths:
        base = root or Path(os.environ.get("INVOICER_DATA_DIR", Path.home() / "InvoiceReceiptManager"))
        data = base / "data"
        return cls(base, data, data / "business.sqlite3", base / "documents",
                   base / "exports", base / "backups", base / "logs")

    def ensure(self) -> AppPaths:
        for path in (self.data, self.documents, self.exports, self.backups, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        for subdir in ("invoices", "receipts", "credit-notes", "attachments"):
            (self.documents / subdir).mkdir(parents=True, exist_ok=True)
        return self

    @property
    def onedrive_warning(self) -> bool:
        return "onedrive" in str(self.root).lower()
