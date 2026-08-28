import pytest
from PySide6.QtWidgets import QApplication

from invoice_manager.persistence.database import Database
from invoice_manager.ui.login import LoginDialog


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.create_schema()
    yield database
    database.engine.dispose()


def test_login_dialog_opens(qtbot, db):
    _ = QApplication.instance() or QApplication([])
    dlg = LoginDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Login — Invoice & Receipt Manager"
    dlg.reject()
