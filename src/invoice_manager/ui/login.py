"""Login and first-run administrator creation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from invoice_manager.application.auth_service import (
    AuthenticatedUser,
    AuthError,
    AuthService,
)
from invoice_manager.domain.validation import ValidationError


class LoginDialog(QDialog):
    """Sign in, or create the first administrator on a new database."""

    def __init__(
        self,
        session: Session,
        parent: QWidget | None = None,
        *,
        auth: AuthService | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._auth = auth if auth is not None else AuthService(session)
        self._first_run = self._auth.requires_first_run_setup()
        self.authenticated_user: AuthenticatedUser | None = None

        self.setWindowTitle("Create Administrator" if self._first_run else "Sign In")
        self.setModal(True)

        self._username = QLineEdit()
        self._username.setObjectName("usernameField")
        self._username.setPlaceholderText("Username")
        self._password = QLineEdit()
        self._password.setObjectName("passwordField")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm = QLineEdit()
        self._confirm.setObjectName("confirmPasswordField")
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._display_name = QLineEdit()
        self._display_name.setObjectName("displayNameField")

        self._message = QLabel()
        self._message.setObjectName("errorMessage")
        self._message.setWordWrap(True)
        self._message.setStyleSheet("color: #b00020;")
        self._message.setVisible(False)

        form = QFormLayout()
        form.addRow("Username", self._username)
        if self._first_run:
            form.addRow("Display name", self._display_name)
        form.addRow("Password", self._password)
        if self._first_run:
            form.addRow("Confirm password", self._confirm)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Create" if self._first_run else "Sign in")
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        if self._first_run:
            intro = QLabel(
                "This computer has no user yet. Create your administrator account to continue."
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self._message)
        layout.addWidget(buttons)

        self._username.setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def is_first_run(self) -> bool:
        return self._first_run

    def _show_error(self, message: str) -> None:
        self._message.setText(message)
        self._message.setVisible(True)

    def submit(self) -> None:
        """Validate the entered credentials and accept the dialog on success."""
        try:
            if self._first_run:
                if self._password.text() != self._confirm.text():
                    self._show_error("The passwords do not match.")
                    return
                self.authenticated_user = self._auth.create_first_admin(
                    self._username.text(),
                    self._password.text(),
                    display_name=self._display_name.text() or None,
                )
            else:
                self.authenticated_user = self._auth.authenticate(
                    self._username.text(), self._password.text()
                )
        except (AuthError, ValidationError) as error:
            self._session.rollback()
            self._show_error(str(error))
            self._password.clear()
            return

        self._session.commit()
        self.accept()
