"""Payments & Receipts page."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, cast

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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.documents.receipt_pdf import generate_receipt_pdf
from invoice_manager.persistence.models import Invoice, Payment
from invoice_manager.ui.app_context import AppContext


class RecordPaymentDialog(QDialog):
    """Record a payment against an issued invoice."""

    def __init__(
        self,
        context: AppContext,
        invoice: Invoice | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._preselected = invoice
        self.setWindowTitle("Record Payment")
        self._build_ui()
        self._load_invoices()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._invoice = QComboBox()
        self._invoice.setEditable(False)
        form.addRow("Invoice:", self._invoice)

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        form.addRow("Payment date:", self._date)

        self._amount = QDoubleSpinBox()
        self._amount.setMaximum(9999999.99)
        self._amount.setMinimum(0.01)
        self._amount.setDecimals(2)
        form.addRow("Amount ($):", self._amount)

        self._method = QComboBox()
        self._method.setEditable(True)
        self._method.addItems(["Cash", "EFT", "Cheque", "Card", "Other"])
        form.addRow("Method:", self._method)

        self._reference = QLineEdit()
        form.addRow("Reference:", self._reference)

        layout.addLayout(form)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _load_invoices(self) -> None:
        if self._preselected is not None:
            inv = self._preselected
            balance = inv.total_cents - sum(
                p.amount_cents for p in inv.payments if not p.is_reversed
            ) - sum(c.amount_cents for c in inv.credits)
            display = f"{inv.number} — {inv.client_name} — ${balance / 100:.2f}"
            self._invoice.addItem(display, inv.id)
            self._invoice.setEnabled(False)
            self._amount.setValue(balance / 100)
            return
        invoices = self._context.invoice_service.list_invoices()
        for inv in invoices:
            if inv.is_void or inv.is_cancelled or inv.status == "paid":
                continue
            display = f"{inv.number} — {inv.client_name} — ${inv.total_cents / 100:.2f}"
            self._invoice.addItem(display, inv.id)

    def _save(self) -> None:
        invoice = self._preselected
        if invoice is None:
            invoice_id = self._invoice.currentData()
            if invoice_id is None:
                QMessageBox.warning(self, "No invoice", "Select an invoice.")
                return
            invoice = self._context.invoice_service.get(int(invoice_id))
        if invoice is None:
            return
        try:
            payment = self._context.payment_service.record(
                invoice=invoice,
                amount_cents=int(self._amount.value() * 100),
                payment_date=cast(date, self._date.date().toPython()),
                method=self._method.currentText(),
                reference=self._reference.text().strip() or None,
            )
            self._context.session.commit()
            self._generate_receipt(payment, invoice)
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))

    def _generate_receipt(self, payment: Payment, invoice: Invoice) -> None:
        settings: dict[str, Any] = {
            k: self._context.setting_repo.get(k)
            for k in [
                "business_name",
                "business_address",
                "thank_you_note",
            ]
        }
        receipt_path = (
            self._context.config.get_data_directory()
            / "documents"
            / "receipts"
            / str(cast(date, payment.date).year)
            / f"{payment.receipt_number}.pdf"
        )
        generate_receipt_pdf(payment, invoice, settings, receipt_path)
        payment.pdf_path = str(receipt_path)
        self._context.session.commit()


class IssueReceiptDialog(QDialog):
    """Generate a receipt PDF for an existing payment."""

    def __init__(
        self,
        context: AppContext,
        invoice: Invoice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._invoice = invoice
        self.setWindowTitle(f"Issue Receipt - {invoice.number}")
        self._build_ui()
        self._load_payments()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Client: {self._invoice.client_name}"))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Receipt #", "Date", "Amount", "PDF"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        btn = QPushButton("Generate Receipt PDF")
        btn.clicked.connect(self._generate)
        layout.addWidget(btn)

    def _load_payments(self) -> None:
        self._payments = list(self._invoice.payments)
        self._table.setRowCount(len(self._payments))
        for row, payment in enumerate(self._payments):
            self._table.setItem(row, 0, QTableWidgetItem(payment.receipt_number or "(not issued)"))
            self._table.setItem(row, 1, QTableWidgetItem(str(payment.date)))
            self._table.setItem(row, 2, QTableWidgetItem(f"${payment.amount_cents / 100:.2f}"))
            self._table.setItem(row, 3, QTableWidgetItem("Yes" if payment.pdf_path else "No"))

    def _selected_payment(self) -> Payment | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._payments[rows[0].row()]

    def _generate(self) -> None:
        payment = self._selected_payment()
        if payment is None:
            QMessageBox.information(self, "Select payment", "Select a payment to receipt.")
            return
        if payment.is_reversed:
            QMessageBox.information(self, "Reversed", "Cannot receipt a reversed payment.")
            return
        try:
            payment.receipt_number = payment.receipt_number or self._context.payment_service._numbering.reserve("receipt")
            self._context.payment_service._persist_numbering()
            settings: dict[str, Any] = {
                k: self._context.setting_repo.get(k)
                for k in [
                    "business_name",
                    "business_address",
                    "thank_you_note",
                ]
            }
            receipt_path = (
                self._context.config.get_data_directory()
                / "documents"
                / "receipts"
                / str(cast(date, payment.date).year)
                / f"{payment.receipt_number}.pdf"
            )
            generate_receipt_pdf(payment, self._invoice, settings, receipt_path)
            payment.pdf_path = str(receipt_path)
            self._context.session.commit()
            self._load_payments()
            QMessageBox.information(self, "Receipt saved", f"Saved {receipt_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Receipt failed", str(exc))


class PaymentsPage(QWidget):
    """Page listing payments and receipts."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._payments: list[Payment] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Payments & Receipts"))

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Record Payment")
        add_btn.clicked.connect(self._record_payment)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Receipt #", "Invoice", "Date", "Client", "Amount", "Method", "PDF"]
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        action_bar = QHBoxLayout()
        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.clicked.connect(self._open_pdf)
        reverse_btn = QPushButton("Reverse")
        reverse_btn.clicked.connect(self._reverse_payment)
        action_bar.addWidget(open_pdf_btn)
        action_bar.addWidget(reverse_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def refresh(self) -> None:
        self._payments = list(
            self._context.payment_repo._session.query(Payment).order_by(Payment.date.desc()).all()
        )
        self._table.setRowCount(len(self._payments))
        for row, payment in enumerate(self._payments):
            invoice = payment.invoice
            client_name = invoice.client_name if invoice else ""
            self._table.setItem(row, 0, QTableWidgetItem(payment.receipt_number or ""))
            self._table.setItem(row, 1, QTableWidgetItem(invoice.number if invoice else ""))
            self._table.setItem(row, 2, QTableWidgetItem(str(payment.date)))
            self._table.setItem(row, 3, QTableWidgetItem(client_name))
            self._table.setItem(row, 4, QTableWidgetItem(f"${payment.amount_cents / 100:.2f}"))
            self._table.setItem(row, 5, QTableWidgetItem(payment.method or ""))
            self._table.setItem(row, 6, QTableWidgetItem("Yes" if payment.pdf_path else "No"))

    def _record_payment(self) -> None:
        dlg = RecordPaymentDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _selected_payment(self) -> Payment | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._payments[rows[0].row()]

    def _open_pdf(self) -> None:
        payment = self._selected_payment()
        if payment is None or not payment.pdf_path:
            QMessageBox.information(self, "No PDF", "Select a payment that has a PDF.")
            return
        path = Path(payment.pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Missing", f"PDF not found: {path}")
            return
        os.startfile(str(path))

    def _reverse_payment(self) -> None:
        payment = self._selected_payment()
        if payment is None:
            QMessageBox.information(self, "Select payment", "Select a payment to reverse.")
            return
        if payment.is_reversed:
            QMessageBox.information(self, "Already reversed", "This payment is already reversed.")
            return
        reason, ok = QInputDialog.getText(self, "Reverse Payment", "Reason for reversal:")
        if not ok or not reason.strip():
            return
        try:
            self._context.payment_service.reverse(payment, reason.strip())
            self._context.session.commit()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reverse failed", str(exc))
