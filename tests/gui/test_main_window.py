from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.ui.main_window import MainWindow


def test_main_window_opens(qtbot, tmp_path):
    config = AppConfig(tmp_path / "app")
    window = MainWindow(config, current_user="admin")
    qtbot.addWidget(window)
    assert window.windowTitle() == "Invoice & Receipt Manager"
    window.close()
