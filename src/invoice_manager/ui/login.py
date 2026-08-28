"""Login dialog and bootstrap flow."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.application.auth_service import AuthService
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import UserRepository


def run_login_flow(config: AppConfig) -> str | None:
    """Show login, create the admin user on first run, and return the username."""
    db = Database(config.db_path())
    db.create_schema()

    session = db.new_session()
    try:
        user_repo = UserRepository(session)
        auth = AuthService(user_repo)
        auth.ensure_default_admin()
        session.commit()

        dialog = LoginDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        username = dialog.username()
        password = dialog.password()
        if not auth.verify(username, password):
            QMessageBox.warning(
                None,
                "Login failed",
                "Incorrect username or password.",
            )
            return None
        return username
    finally:
        session.close()


class LoginDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Login — Invoice & Receipt Manager")
        self.setMinimumWidth(320)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please sign in."))

        form = QFormLayout()
        self._username = QLineEdit()
        self._username.setPlaceholderText("admin")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Admin")
        form.addRow("Username:", self._username)
        form.addRow("Password:", self._password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def username(self) -> str:
        return self._username.text().strip()

    def password(self) -> str:
        return self._password.text()
