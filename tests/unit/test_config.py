import json
from pathlib import Path

from invoice_manager.config import AppPaths, AppSettings


def test_currency_symbol_defaults_to_dollar(tmp_path: Path) -> None:
    assert AppSettings.load(tmp_path / "settings.json").currency_symbol == "$"


def test_currency_symbol_is_loaded_from_settings(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"currency_symbol": "A$"}), encoding="utf-8")
    assert AppSettings.load(settings).currency_symbol == "A$"


def test_managed_storage_layout_is_created(tmp_path: Path) -> None:
    paths = AppPaths.resolve(tmp_path).ensure()

    for directory in (paths.data, paths.documents, paths.exports, paths.backups, paths.logs):
        assert directory.is_dir()
    for subdir in ("invoices", "receipts", "credit-notes", "attachments"):
        assert (paths.documents / subdir).is_dir()
    assert paths.database.parent == paths.data
    assert paths.backups != paths.data


def test_data_dir_environment_override_and_onedrive_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INVOICER_DATA_DIR", str(tmp_path / "OneDrive" / "Invoicer"))

    paths = AppPaths.resolve()

    assert paths.root == tmp_path / "OneDrive" / "Invoicer"
    assert paths.onedrive_warning is True
    assert AppPaths.resolve(tmp_path).onedrive_warning is False
