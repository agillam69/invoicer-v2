"""Dialog for recording a manual/historical invoice."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.persistence.models import Client
from invoice_manager.ui.app_context import AppContext


class ManualInvoiceDialog(QDialog):
    """Record an invoice that was created outside the application."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._clients: list[Client] = []
        self.setWindowTitle("Record Manual Invoice")
        self.setMinimumSize(500, 480)
        self._build_ui()
        self._load_clients()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._number = QLineEdit()
        self._number.setPlaceholderText("e.g. INV-0005 or 0005")
        form.addRow("Invoice number:", self._number)

        self._client = QComboBox()
        self._client.setEditable(True)
        self._client.currentTextChanged.connect(self._on_client_changed)
        form.addRow("Client:", self._client)

        self._client_address = QLineEdit()
        form.addRow("Client address:", self._client_address)

        self._issue_date = QDateEdit()
        self._issue_date.setCalendarPopup(True)
        self._issue_date.setDate(QDate.currentDate())
        form.addRow("Invoice date:", self._issue_date)

        self._due_date = QDateEdit()
        self._due_date.setCalendarPopup(True)
        self._due_date.setDate(QDate.currentDate().addDays(7))
        form.addRow("Due date:", self._due_date)

        self._subtotal = QLineEdit("0.00")
        form.addRow("Subtotal ($):", self._subtotal)

        self._gst = QLineEdit("0.00")
        form.addRow("GST ($):", self._gst)

        self._total = QLineEdit("0.00")
        form.addRow("Total ($):", self._total)

        self._paid = QCheckBox("Already paid")
        self._paid.stateChanged.connect(self._on_paid_changed)
        form.addRow(self._paid)

        self._paid_date = QDateEdit()
        self._paid_date.setCalendarPopup(True)
        self._paid_date.setDate(QDate.currentDate())
        self._paid_date.setEnabled(False)
        form.addRow("Paid date:", self._paid_date)

        self._payment_note = QLineEdit()
        form.addRow("Payment note:", self._payment_note)

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

    def _load_clients(self) -> None:
        self._clients = self._context.client_repo.list_active()
        for client in self._clients:
            self._client.addItem(client.name, client.id)

    def _on_client_changed(self, text: str) -> None:
        for client in self._clients:
            if client.name == text:
                self._client_address.setText(client.address or "")
                return

    def _on_paid_changed(self, state: int) -> None:
        self._paid_date.setEnabled(state != 0)

    def _to_cents(self, text: str) -> int:
        try:
            return int(
                (Decimal(text.strip() or "0") * 100).to_integral_value(
                    rounding=ROUND_HALF_UP
                )
            )
        except Exception:
            return 0

    def _save(self) -> None:
        number = self._number.text().strip()
        client_name = self._client.currentText().strip()
        if not number or not client_name:
            QMessageBox.warning(self, "Missing", "Invoice number and client are required.")
            return

        subtotal = self._to_cents(self._subtotal.text())
        gst = self._to_cents(self._gst.text())
        total = self._to_cents(self._total.text())
        if total <= 0:
            QMessageBox.warning(self, "Invalid", "Total must be greater than zero.")
            return

        try:
            invoice = self._context.invoice_service.record_manual_invoice(
                number=number,
                client_name=client_name,
                client_address=self._client_address.text().strip() or None,
                issue_date=cast(date, self._issue_date.date().toPython()),
                due_date=cast(date, self._due_date.date().toPython()),
                subtotal_cents=subtotal,
                gst_cents=gst,
                total_cents=total,
                notes=self._notes.toPlainText().strip() or None,
                paid=self._paid.isChecked(),
                paid_date=(
                    cast(date, self._paid_date.date().toPython())
                    if self._paid.isChecked()
                    else None
                ),
                payment_note=self._payment_note.text().strip() or None,
            )
            self._context.session.commit()
            QMessageBox.information(self, "Saved", f"Invoice {invoice.number} recorded.")
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Failed", str(exc))
