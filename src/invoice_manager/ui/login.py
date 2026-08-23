from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class LoginDialog(QDialog):
    authenticated = Signal(object)

    def __init__(self, service: Any, session: Any) -> None:
        super().__init__()
        self.service = service
        self.session = session
        self.setWindowTitle("Invoicer V2 — Sign in")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #b00020;")
        self.error_label.setWordWrap(True)
        submit = QPushButton("Sign in")
        submit.clicked.connect(self._submit)
        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(submit)
        self._submit_button = submit

    def _submit(self) -> None:
        try:
            user = self.service.authenticate(
                self.session, self.username.text(), self.password.text()
            )
        except ValueError:
            self.password.clear()
            self.error_label.setText("Invalid username or password.")
            return
        self.error_label.clear()
        self.session.commit()
        self.authenticated.emit(user)
        self.accept()


class FirstRunDialog(QDialog):
    def __init__(self, service: Any, session: Any) -> None:
        super().__init__()
        self.service = service
        self.session = session
        self.setWindowTitle("Invoicer V2 — Create administrator")
        self.username = QLineEdit()
        self.display_name = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        submit = QPushButton("Create administrator")
        submit.clicked.connect(self._submit)
        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Display name", self.display_name)
        form.addRow("Password", self.password)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(submit)

    def _submit(self) -> None:
        try:
            self.service.create_first_admin(
                self.session,
                self.username.text(),
                self.display_name.text(),
                self.password.text(),
            )
        except ValueError:
            self.setWindowTitle("Invoicer V2 — Enter all administrator details")
            return
        self.accept()
