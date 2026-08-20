from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from invoice_manager.domain.validation import validate_filename, validate_relative_path


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def managed_path(self, relative_path: str) -> Path:
        if not validate_relative_path(relative_path):
            raise ValueError("unsafe managed path")
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("managed path escapes storage")
        return path

    def copy_in(self, source: Path, relative_path: str) -> tuple[Path, str]:
        if not source.is_file():
            raise FileNotFoundError(source)
        if not validate_filename(source.name):
            raise ValueError("unsafe source filename")
        destination = self.managed_path(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination, self.sha256(destination)

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
