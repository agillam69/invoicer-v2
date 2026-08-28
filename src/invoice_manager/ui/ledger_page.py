"""Ledger page for income and expense entries."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
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

_LEDGER_INCOME_CATEGORIES = ["Invoice Payment", "Sales", "Interest", "Other Income", "Other"]
_LEDGER_EXPENSE_CATEGORIES = [
    "Advertising",
    "Bank Fees",
    "Insurance",
    "Office Supplies",
    "Rent",
    "Repairs",
    "Utilities",
    "Wages",
    "Other Expense",
    "Other",
]


class LedgerEntryDialog(QDialog):
    """Dialog to add or edit a ledger entry."""

    def __init__(
        self,
        context: AppContext,
        entry: LedgerEntry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._entry = entry
        self.setWindowTitle("Edit Ledger Entry" if entry else "Add Ledger Entry")
        self._build_ui()
        self._load_entry()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        form.addRow("Date:", self._date)

        self._type = QComboBox()
        self._type.addItems(["Income", "Expense"])
        self._type.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type:", self._type)

        self._category = QComboBox()
        self._category.setEditable(True)
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

    def _on_type_changed(self, text: str) -> None:
        self._category.clear()
        items = _LEDGER_INCOME_CATEGORIES if text == "Income" else _LEDGER_EXPENSE_CATEGORIES
        self._category.addItems(items)

    def _load_entry(self) -> None:
        if self._entry is None:
            self._on_type_changed("Income")
            return
        self._date.setDate(QDate.fromString(str(self._entry.date), "yyyy-MM-dd"))
        self._type.setCurrentText("Income" if self._entry.entry_type == "in" else "Expense")
        self._category.setEditText(self._entry.category)
        self._description.setText(self._entry.description)
        self._amount.setValue(self._entry.amount_cents / 100)
        self._reference.setText(self._entry.reference or "")
        self._notes.setPlainText(self._entry.notes or "")

    def _save(self) -> None:
        entry_type = "in" if self._type.currentText() == "Income" else "out"
        category = self._category.currentText().strip() or "Other"
        description = self._description.text().strip() or "Entry"
        amount_cents = int(self._amount.value() * 100)
        reference = self._reference.text().strip() or None
        notes = self._notes.toPlainText().strip() or None
        entry_date = cast(date, self._date.date().toPython())
        try:
            if self._entry is None:
                self._context.ledger_service.add_entry(
                    entry_date=entry_date,
                    entry_type=entry_type,
                    category=category,
                    description=description,
                    amount_cents=amount_cents,
                    reference=reference,
                    notes=notes,
                )
            else:
                self._context.ledger_service.update_entry(
                    entry=self._entry,
                    entry_date=entry_date,
                    entry_type=entry_type,
                    category=category,
                    description=description,
                    amount_cents=amount_cents,
                    reference=reference,
                    notes=notes,
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
        import_btn = QPushButton("Import CSV")
        import_btn.clicked.connect(self._import_csv)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(export_btn)
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

        action_bar = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_entry)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_entry)
        action_bar.addWidget(edit_btn)
        action_bar.addWidget(delete_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

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
        dlg = LedgerEntryDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _edit_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Select entry", "Select a ledger entry to edit.")
            return
        dlg = LedgerEntryDialog(self._context, entry=entry, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _delete_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Select entry", "Select a ledger entry to delete.")
            return
        reason, ok = QInputDialog.getText(
            self,
            "Delete Ledger Entry",
            "Optional reason for deletion (will be logged):",
        )
        if not ok:
            return
        if (
            QMessageBox.question(
                self,
                "Confirm delete",
                "Delete this ledger entry?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._context.ledger_service.delete_entry(entry, reason.strip() or None)
        self._context.session.commit()
        self.refresh()

    def _selected_entry(self) -> LedgerEntry | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._entries[rows[0].row()]

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Ledger CSV",
            str(self._context.config.get_exports_directory() / "ledger.csv"),
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with Path(path).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "date",
                        "entry_type",
                        "category",
                        "description",
                        "amount",
                        "reference",
                        "notes",
                    ]
                )
                for entry in self._entries:
                    writer.writerow(
                        [
                            entry.date,
                            entry.entry_type,
                            entry.category,
                            entry.description,
                            f"{entry.amount_cents / 100:.2f}",
                            entry.reference or "",
                            entry.notes or "",
                        ]
                    )
            QMessageBox.information(self, "Exported", f"Saved {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Ledger CSV",
            str(self._context.config.get_exports_directory()),
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with Path(path).open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    entry_date = self._parse_date(row.get("date", ""))
                    if entry_date is None:
                        continue
                    entry_type = (row.get("entry_type") or "").strip().lower()
                    if entry_type not in ("in", "out"):
                        t = (row.get("type") or "").strip().lower()
                        if t == "income" or t == "in":
                            entry_type = "in"
                        elif t == "expense" or t == "out":
                            entry_type = "out"
                        else:
                            continue
                    amount = self._parse_amount(row.get("amount", "0"))
                    if amount <= 0:
                        continue
                    self._context.ledger_service.add_entry(
                        entry_date=entry_date,
                        entry_type=entry_type,
                        category=(row.get("category") or "Other").strip() or "Other",
                        description=(row.get("description") or "").strip() or "Imported",
                        amount_cents=amount,
                        reference=(row.get("reference") or "").strip() or None,
                        notes=(row.get("notes") or "").strip() or None,
                    )
                    count += 1
            self._context.session.commit()
            QMessageBox.information(self, "Imported", f"Imported {count} entries.")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", str(exc))

    def _parse_date(self, value: str) -> date | None:
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
        return None

    def _parse_amount(self, value: str) -> int:
        try:
            cleaned = value.replace(",", "").replace("$", "").strip()
            return int(round(float(cleaned) * 100))
        except (ValueError, TypeError):
            return 0
