from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout


class LoginDialog(QDialog):
    authenticated = Signal(object)

    def __init__(self, service: object, session: object) -> None:
        super().__init__()
        self.service = service
        self.session = session
        self.setWindowTitle("Invoicer V2 — Sign in")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        submit = QPushButton("Sign in")
        submit.clicked.connect(self._submit)
        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(submit)
        self._submit_button = submit

    def _submit(self) -> None:
        try:
            user = self.service.authenticate(self.session, self.username.text(), self.password.text())
        except ValueError:
            self.password.clear()
            self.setWindowTitle("Invoicer V2 — Sign in (invalid credentials)")
            return
        self.authenticated.emit(user)
        self.accept()
