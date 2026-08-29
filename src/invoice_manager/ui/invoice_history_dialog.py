"""Dialog showing the audit history for a single invoice."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.persistence.models import Invoice
from invoice_manager.ui.app_context import AppContext


class InvoiceHistoryDialog(QDialog):
    """Display audit events for the selected invoice."""

    def __init__(
        self,
        context: AppContext,
        invoice: Invoice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._invoice = invoice
        self.setWindowTitle(f"Invoice History — {invoice.number}")
        self.setMinimumSize(600, 350)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Client: {self._invoice.client_name} — Total: ${self._invoice.total_cents / 100:.2f}")
        )

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Timestamp", "User", "Action", "Detail"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    def _load(self) -> None:
        entries: list[Any] = []
        entries.extend(
            self._context.audit.list_for_record("invoices", self._invoice.id)
        )
        for payment in self._invoice.payments:
            entries.extend(
                self._context.audit.list_for_record("payments", payment.id)
            )
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(str(entry.timestamp)))
            self._table.setItem(row, 1, QTableWidgetItem(entry.user or ""))
            self._table.setItem(row, 2, QTableWidgetItem(entry.action))
            self._table.setItem(row, 3, QTableWidgetItem(entry.detail or ""))
