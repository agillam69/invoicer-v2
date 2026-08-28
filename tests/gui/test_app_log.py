from pathlib import Path

import pytest

from invoice_manager.ui.app_log import AppLogDialog


@pytest.mark.gui
def test_app_log_filters_by_level_and_search(qtbot, tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text(
        "2026-06-25 INFO started\n2026-06-25 ERROR failed to save\n",
        encoding="utf-8",
    )
    dialog = AppLogDialog(log_path)
    qtbot.addWidget(dialog)
    dialog.level.setCurrentText("ERROR")
    dialog.search.setText("save")
    assert dialog.output.toPlainText() == "2026-06-25 ERROR failed to save"
