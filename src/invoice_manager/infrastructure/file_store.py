"""Managed file storage and hashing for linked documents."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path


class FileStore:
    """Copies linked files into a managed documents tree and records hashes."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.attachments_dir = self.base_dir / "documents" / "attachments"
        self.invoices_dir = self.base_dir / "documents" / "invoices"
        self.receipts_dir = self.base_dir / "documents" / "receipts"
        self.credit_notes_dir = self.base_dir / "documents" / "credit-notes"
        for directory in (
            self.attachments_dir,
            self.invoices_dir,
            self.receipts_dir,
            self.credit_notes_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def import_invoice_pdf(self, source: Path, invoice_number: str) -> Path | None:
        """Copy an invoice PDF into the managed invoices tree."""
        source = Path(source)
        if not source.exists():
            return None
        year = datetime.now().year
        dest_dir = self.invoices_dir / str(year)
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_number = "".join(c for c in invoice_number if c.isalnum() or c in "-_")
        dest = dest_dir / f"{safe_number}.pdf"
        shutil.copy2(source, dest)
        return dest

    def import_file(
        self,
        source: Path,
        *,
        entity_type: str,
        entity_id: int,
        description: str | None = None,
    ) -> Path | None:
        """Copy an arbitrary attachment into managed storage."""
        source = Path(source)
        if not source.exists():
            return None
        sha = self.hash_file(source)
        dest_dir = self.attachments_dir / sha[:2]
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = source.suffix
        dest = dest_dir / f"{sha}{ext}"
        if not dest.exists():
            shutil.copy2(source, dest)
        return dest
