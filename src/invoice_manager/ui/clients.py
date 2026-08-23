from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from invoice_manager.application.client_service import ClientService
from invoice_manager.persistence.models import Client


class ClientsView(QWidget):
    def __init__(
        self, session: Session | None = None, service: ClientService | None = None
    ) -> None:
        super().__init__()
        self.session = session
        self.service = service or ClientService()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search clients")
        self.search.textChanged.connect(self.refresh)
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Email", self.email)
        form.addRow("Phone", self.phone)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Client", "Contact", "Phone", "Email", "Invoices", "Billed", "Balance"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._load_selected)
        add = QPushButton("Add client")
        add.clicked.connect(self._create)
        edit = QPushButton("Save changes")
        edit.clicked.connect(self._update)
        deactivate = QPushButton("Deactivate")
        deactivate.clicked.connect(self._deactivate)
        export = QPushButton("Export / copy CSV")
        export.clicked.connect(self._copy_export)
        actions = QHBoxLayout()
        for button in (add, edit, deactivate, export):
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Clients"))
        layout.addWidget(self.search)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        self._selected: Client | None = None
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self.session is None:
            return
        for client in self.service.list(self.session, self.search.text()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            rollup = self.service.rollup(self.session, client)
            values = [
                client.display_name,
                client.contact_name,
                client.phone,
                client.email,
                str(rollup["invoice_count"]),
                str(rollup["billed_cents"]),
                str(rollup["balance_cents"]),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _load_selected(self, row: int, _column: int) -> None:
        if self.session is None:
            return
        clients = self.service.list(self.session, self.search.text())
        if row >= len(clients):
            return
        self._selected = clients[row]
        self.name.setText(self._selected.display_name)
        self.email.setText(self._selected.email)
        self.phone.setText(self._selected.phone)

    def _create(self) -> None:
        if self.session is None:
            return
        try:
            self.service.create(
                self.session,
                display_name=self.name.text(),
                email=self.email.text(),
                phone=self.phone.text(),
            )
            self.session.commit()
            self._clear_form()
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Client", str(exc))

    def _update(self) -> None:
        if self.session is None or self._selected is None:
            return
        try:
            self.service.update(
                self.session,
                self._selected,
                display_name=self.name.text(),
                email=self.email.text(),
                phone=self.phone.text(),
            )
            self.session.commit()
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Client", str(exc))

    def _deactivate(self) -> None:
        if self.session is None or self._selected is None:
            return
        self.service.deactivate(self.session, self._selected)
        self.session.commit()
        self.refresh()

    def _copy_export(self) -> None:
        if self.session is not None:
            QApplication.clipboard().setText(self.service.export_csv(self.session))

    def _clear_form(self) -> None:
        self.name.clear()
        self.email.clear()
        self.phone.clear()
        self._selected = None
