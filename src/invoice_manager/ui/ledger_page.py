"""Ledger page for income and expense entries."""

from __future__ import annotations

from datetime import date
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.persistence.models import LedgerEntry
from invoice_manager.ui.app_context import AppContext


class AddLedgerEntryDialog(QDialog):
    """Dialog to add a new ledger entry."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("Add Ledger Entry")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        form.addRow("Date:", self._date)

        self._type = QComboBox()
        self._type.addItems(["Income", "Expense"])
        form.addRow("Type:", self._type)

        self._category = QLineEdit()
        self._category.setText("Other")
        form.addRow("Category:", self._category)

        self._description = QLineEdit()
        form.addRow("Description:", self._description)

        self._amount = QDoubleSpinBox()
        self._amount.setMaximum(9999999.99)
        self._amount.setMinimum(0.01)
        self._amount.setDecimals(2)
        form.addRow("Amount ($):", self._amount)

        self._reference = QLineEdit()
        form.addRow("Reference:", self._reference)

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)
        form.addRow("Notes:", self._notes)

        layout.addLayout(form)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _save(self) -> None:
        entry_type = "in" if self._type.currentText() == "Income" else "out"
        try:
            self._context.ledger_service.add_entry(
                entry_date=cast(date, self._date.date().toPython()),
                entry_type=entry_type,
                category=self._category.text().strip() or "Other",
                description=self._description.text().strip() or "Entry",
                amount_cents=int(self._amount.value() * 100),
                reference=self._reference.text().strip() or None,
                notes=self._notes.toPlainText().strip() or None,
            )
            self._context.session.commit()
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))


class LedgerPage(QWidget):
    """Page listing ledger entries."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._entries: list[LedgerEntry] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Income & Expenses"))

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add entry")
        add_btn.clicked.connect(self._add_entry)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Type", "Category", "Description", "Amount", "Reference"]
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._entries = self._context.ledger_service.list_entries()
        self._table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            self._table.setItem(row, 0, QTableWidgetItem(str(entry.date)))
            self._table.setItem(row, 1, QTableWidgetItem(entry.entry_type.upper()))
            self._table.setItem(row, 2, QTableWidgetItem(entry.category))
            self._table.setItem(row, 3, QTableWidgetItem(entry.description))
            self._table.setItem(row, 4, QTableWidgetItem(f"${entry.amount_cents / 100:.2f}"))
            self._table.setItem(row, 5, QTableWidgetItem(entry.reference or ""))

    def _add_entry(self) -> None:
        dlg = AddLedgerEntryDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()
