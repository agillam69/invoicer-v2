import pytest

from invoice_manager.application.auth import AuthenticationError
from invoice_manager.ui.login import LoginDialog


class FailingAuthService:
    def authenticate(self, session, username: str, password: str) -> None:
        raise AuthenticationError("invalid username or password")


@pytest.mark.gui
def test_login_failure_is_visible_and_generic(qtbot) -> None:
    dialog = LoginDialog(FailingAuthService(), object())
    qtbot.addWidget(dialog)
    dialog.username.setText("unknown")
    dialog.password.setText("wrong")
    dialog._submit()
    first_message = dialog.error_label.text()
    assert first_message == "Invalid username or password."
    dialog.username.setText("known")
    dialog.password.setText("another-wrong")
    dialog._submit()
    assert dialog.error_label.text() == first_message
