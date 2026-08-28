"""Dialog for applying a credit note to an invoice."""

from __future__ import annotations

from datetime import date
from typing import cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.domain.money import to_cents
from invoice_manager.persistence.models import Invoice
from invoice_manager.ui.app_context import AppContext


class CreditNoteDialog(QDialog):
    """Create a credit note for an issued invoice."""

    def __init__(self, context: AppContext, invoice: Invoice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._invoice = invoice
        self.setWindowTitle(f"Credit Note - {invoice.number}")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        paid = sum(p.amount_cents for p in self._invoice.payments if not p.is_reversed)
        credits = sum(c.amount_cents for c in self._invoice.credits)
        balance = self._invoice.total_cents - paid - credits

        form.addRow("Invoice:", QLabel(self._invoice.number))
        form.addRow("Client:", QLabel(self._invoice.client_name))
        form.addRow("Balance:", QLabel(f"${balance / 100:.2f}"))
        self._balance_cents = balance

        self._amount = QLineEdit()
        self._amount.setPlaceholderText("0.00")
        form.addRow("Credit amount:", self._amount)

        self._reason = QLineEdit()
        form.addRow("Reason:", self._reason)

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        form.addRow("Date:", self._date)

        layout.addLayout(form)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _save(self) -> None:
        amount_cents = to_cents(self._amount.text().strip())
        if amount_cents <= 0:
            QMessageBox.warning(self, "Invalid amount", "Enter a positive credit amount.")
            return
        if amount_cents > self._balance_cents:
            QMessageBox.warning(self, "Too large", "Credit amount cannot exceed the invoice balance.")
            return
        reason = self._reason.text().strip()
        if not reason:
            QMessageBox.warning(self, "Reason required", "Enter a reason for the credit note.")
            return
        credit_date = cast(date, self._date.date().toPython())
        try:
            self._context.invoice_service.add_credit_note(
                self._invoice,
                amount_cents,
                reason,
                credit_date,
            )
            self._context.session.commit()
            QMessageBox.information(self, "Credit note saved", f"Created {self._invoice.credits[-1].number}")
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Credit note failed", str(exc))
