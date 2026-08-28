"""Clients management page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.persistence.models import Client
from invoice_manager.ui.app_context import AppContext


class ClientDialog(QDialog):
    """Add or edit a client."""

    def __init__(
        self,
        context: AppContext,
        client: Client | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._client = client
        self.setWindowTitle("Edit Client" if client else "Add Client")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit()
        self._contact = QLineEdit()
        self._phone = QLineEdit()
        self._email = QLineEdit()
        self._address = QLineEdit()

        form.addRow("Name:", self._name)
        form.addRow("Contact:", self._contact)
        form.addRow("Phone:", self._phone)
        form.addRow("Email:", self._email)
        form.addRow("Address:", self._address)
        layout.addLayout(form)

        if self._client is not None:
            self._name.setText(self._client.name)
            self._contact.setText(self._client.contact_name or "")
            self._phone.setText(self._client.phone or "")
            self._email.setText(self._client.email or "")
            self._address.setText(self._client.address or "")

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Client name is required.")
            return
        if self._client is None:
            self._context.client_repo.create(
                name=name,
                contact_name=self._contact.text().strip() or None,
                phone=self._phone.text().strip() or None,
                email=self._email.text().strip() or None,
                address=self._address.text().strip() or None,
            )
        else:
            self._client.name = name
            self._client.contact_name = self._contact.text().strip() or None
            self._client.phone = self._phone.text().strip() or None
            self._client.email = self._email.text().strip() or None
            self._client.address = self._address.text().strip() or None
        self._context.session.commit()
        self.accept()


class ClientsPage(QWidget):
    """Page for listing and managing clients."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._clients: list[Client] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Clients"))

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add client")
        add_btn.clicked.connect(self._add_client)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Contact", "Phone", "Email"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        action_bar = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_client)
        action_bar.addWidget(edit_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def refresh(self) -> None:
        self._clients = self._context.client_repo.list_active()
        self._table.setRowCount(len(self._clients))
        for row, client in enumerate(self._clients):
            self._table.setItem(row, 0, QTableWidgetItem(client.name))
            self._table.setItem(row, 1, QTableWidgetItem(client.contact_name or ""))
            self._table.setItem(row, 2, QTableWidgetItem(client.phone or ""))
            self._table.setItem(row, 3, QTableWidgetItem(client.email or ""))

    def _selected_client(self) -> Client | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._clients[rows[0].row()]

    def _add_client(self) -> None:
        dlg = ClientDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _edit_client(self) -> None:
        client = self._selected_client()
        if client is None:
            QMessageBox.information(self, "Select client", "Select a client to edit.")
            return
        dlg = ClientDialog(self._context, client=client, parent=self)
        if dlg.exec() == 1:
            self.refresh()
