import json
from pathlib import Path

from invoice_manager.config import AppSettings


def test_currency_symbol_defaults_to_dollar(tmp_path: Path) -> None:
    assert AppSettings.load(tmp_path / "settings.json").currency_symbol == "$"


def test_currency_symbol_is_loaded_from_settings(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"currency_symbol": "A$"}), encoding="utf-8")
    assert AppSettings.load(settings).currency_symbol == "A$"
