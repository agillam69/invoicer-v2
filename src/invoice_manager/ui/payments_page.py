"""Payments & Receipts page."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QDate, Qt
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
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.documents.receipt_docx import generate_receipt_docx
from invoice_manager.documents.receipt_pdf import generate_receipt_pdf
from invoice_manager.documents.receipt_xlsx import generate_receipt_xlsx
from invoice_manager.persistence.models import Client, Invoice, Payment, Receipt
from invoice_manager.ui.app_context import AppContext


def _receipt_settings(context: AppContext) -> dict[str, Any]:
    keys = [
        "business_name",
        "business_address",
        "business_abn",
        "business_phone",
        "business_email",
        "receipt_title",
        "receipt_invoice_label",
        "receipt_date_label",
        "receipt_amount_label",
        "receipt_method_label",
        "receipt_reference_label",
        "receipt_thank_you",
    ]
    return {key: context.setting_repo.get(key) for key in keys}


class ManualReceiptDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._clients: list[Client] = context.client_repo.list_active()
        self.setWindowTitle("Create Manual Receipt")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._client = QComboBox()
        self._client.setEditable(True)
        self._client.addItem("", None)
        for client in self._clients:
            self._client.addItem(client.name, client.id)
        self._client.currentIndexChanged.connect(self._client_changed)
        form.addRow("Received from:", self._client)
        self._address = QLineEdit()
        form.addRow("Address:", self._address)
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        form.addRow("Receipt date:", self._date)
        self._amount = QDoubleSpinBox()
        self._amount.setRange(0.01, 9999999.99)
        self._amount.setDecimals(2)
        form.addRow("Amount ($):", self._amount)
        self._method = QComboBox()
        self._method.setEditable(True)
        self._method.addItems(["Cash", "EFT", "Cheque", "Card", "Other"])
        form.addRow("Method:", self._method)
        self._reference = QLineEdit()
        form.addRow("Reference:", self._reference)
        self._description = QLineEdit()
        form.addRow("Received for:", self._description)
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(70)
        form.addRow("Notes:", self._notes)
        layout.addLayout(form)
        self._formats = QComboBox()
        self._formats.addItems(["PDF", "Word", "Excel", "All formats"])
        form.addRow("Generate:", self._formats)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _client_changed(self) -> None:
        client_id = self._client.currentData()
        client = next((item for item in self._clients if item.id == client_id), None)
        if client is not None:
            self._address.setText(client.address or "")

    def _save(self) -> None:
        try:
            receipt = self._context.payment_service.record_manual_receipt(
                client_name=self._client.currentText(),
                client_id=self._client.currentData(),
                client_address=self._address.text().strip() or None,
                amount_cents=int(self._amount.value() * 100),
                receipt_date=cast(date, self._date.date().toPython()),
                method=self._method.currentText(),
                reference=self._reference.text().strip() or None,
                description=self._description.text().strip() or None,
                notes=self._notes.toPlainText().strip() or None,
            )
            self._context.session.commit()
            receipt_date = cast(date, receipt.date)
            folder = (
                self._context.config.get_documents_directory()
                / "receipts"
                / str(receipt_date.year)
            )
            settings = _receipt_settings(self._context)
            selected = self._formats.currentText()
            generated: list[Path] = []
            if selected in {"PDF", "All formats"}:
                path = folder / f"{receipt.number}.pdf"
                generate_receipt_pdf(receipt, None, settings, path)
                receipt.pdf_path = str(path)
                generated.append(path)
            if selected in {"Word", "All formats"}:
                path = folder / f"{receipt.number}.docx"
                generate_receipt_docx(receipt, None, settings, path)
                receipt.docx_path = str(path)
                generated.append(path)
            if selected in {"Excel", "All formats"}:
                path = folder / f"{receipt.number}.xlsx"
                generate_receipt_xlsx(receipt, None, settings, path)
                receipt.xlsx_path = str(path)
                generated.append(path)
            self._context.session.commit()
            if generated:
                os.startfile(str(generated[0]))
            self.accept()
        except Exception as exc:  # noqa: BLE001
            self._context.session.rollback()
            QMessageBox.warning(self, "Receipt failed", str(exc))


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
                "receipt_title",
                "receipt_invoice_label",
                "receipt_date_label",
                "receipt_amount_label",
                "receipt_method_label",
                "receipt_reference_label",
                "receipt_thank_you",
            ]
        }
        receipt_path = (
            self._context.config.get_documents_directory()
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

        actions = QHBoxLayout()
        pdf_btn = QPushButton("Generate PDF")
        pdf_btn.clicked.connect(lambda: self._generate("pdf"))
        word_btn = QPushButton("Generate Word")
        word_btn.clicked.connect(lambda: self._generate("docx"))
        excel_btn = QPushButton("Generate Excel")
        excel_btn.clicked.connect(lambda: self._generate("xlsx"))
        actions.addWidget(pdf_btn)
        actions.addWidget(word_btn)
        actions.addWidget(excel_btn)
        layout.addLayout(actions)

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

    def _generate(self, extension: str) -> None:
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
            settings = _receipt_settings(self._context)
            receipt_path = (
                self._context.config.get_documents_directory()
                / "receipts"
                / str(cast(date, payment.date).year)
                / f"{payment.receipt_number}.{extension}"
            )
            if extension == "pdf":
                generate_receipt_pdf(payment, self._invoice, settings, receipt_path)
                payment.pdf_path = str(receipt_path)
            elif extension == "docx":
                generate_receipt_docx(payment, self._invoice, settings, receipt_path)
            else:
                generate_receipt_xlsx(payment, self._invoice, settings, receipt_path)
            self._context.session.commit()
            self._load_payments()
            os.startfile(str(receipt_path))
            QMessageBox.information(self, "Receipt saved", f"Saved {receipt_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Receipt failed", str(exc))


class PaymentsPage(QWidget):
    """Page listing payments and receipts."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._payments: list[Payment] = []
        self._receipts: list[Receipt] = []
        self._records: list[Payment | Receipt] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Payments & Receipts"))

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Record Payment")
        add_btn.clicked.connect(self._record_payment)
        manual_btn = QPushButton("Manual Receipt")
        manual_btn.clicked.connect(self._manual_receipt)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(manual_btn)
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
        self._table.doubleClicked.connect(self._open_pdf)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._table)

        action_bar = QHBoxLayout()
        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.clicked.connect(self._open_pdf)
        pdf_btn = QPushButton("Generate PDF")
        pdf_btn.clicked.connect(lambda: self._generate_selected("pdf"))
        word_btn = QPushButton("Generate Word")
        word_btn.clicked.connect(lambda: self._generate_selected("docx"))
        excel_btn = QPushButton("Generate Excel")
        excel_btn.clicked.connect(lambda: self._generate_selected("xlsx"))
        reverse_btn = QPushButton("Reverse")
        reverse_btn.clicked.connect(self._reverse_payment)
        action_bar.addWidget(open_pdf_btn)
        action_bar.addWidget(pdf_btn)
        action_bar.addWidget(word_btn)
        action_bar.addWidget(excel_btn)
        action_bar.addWidget(reverse_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def refresh(self) -> None:
        self._payments = list(
            self._context.payment_repo._session.query(Payment).order_by(Payment.date.desc()).all()
        )
        self._receipts = self._context.payment_service.list_manual_receipts()
        self._records = sorted(
            [*self._payments, *self._receipts], key=lambda record: cast(date, record.date), reverse=True
        )
        self._table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            if isinstance(record, Payment):
                invoice = record.invoice
                number = record.receipt_number or ""
                invoice_number = invoice.number if invoice else ""
                client_name = invoice.client_name if invoice else ""
            else:
                number = record.number
                invoice_number = "Manual"
                client_name = record.client_name
            self._table.setItem(row, 0, QTableWidgetItem(number))
            self._table.setItem(row, 1, QTableWidgetItem(invoice_number))
            self._table.setItem(row, 2, QTableWidgetItem(str(record.date)))
            self._table.setItem(row, 3, QTableWidgetItem(client_name))
            self._table.setItem(row, 4, QTableWidgetItem(f"${record.amount_cents / 100:.2f}"))
            self._table.setItem(row, 5, QTableWidgetItem(record.method or ""))
            self._table.setItem(row, 6, QTableWidgetItem("Yes" if record.pdf_path else "No"))

    def _record_payment(self) -> None:
        dlg = RecordPaymentDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _manual_receipt(self) -> None:
        dlg = ManualReceiptDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _selected_record(self) -> Payment | Receipt | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._records[rows[0].row()]

    def _selected_payment(self) -> Payment | None:
        record = self._selected_record()
        return record if isinstance(record, Payment) else None

    def _context_menu(self, position: Any) -> None:
        menu = QMenu(self)
        menu.addAction("Open PDF", self._open_pdf)
        menu.addAction("Generate PDF", lambda: self._generate_selected("pdf"))
        menu.addAction("Generate Word", lambda: self._generate_selected("docx"))
        menu.addAction("Generate Excel", lambda: self._generate_selected("xlsx"))
        menu.addAction("Reverse", self._reverse_payment)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _open_pdf(self) -> None:
        record = self._selected_record()
        if record is None or not record.pdf_path:
            QMessageBox.information(self, "No PDF", "Select a receipt that has a PDF.")
            return
        path = Path(record.pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Missing", f"PDF not found: {path}")
            return
        os.startfile(str(path))

    def _generate_selected(self, extension: str) -> None:
        record = self._selected_record()
        if record is None:
            QMessageBox.information(self, "Select receipt", "Select a payment or receipt.")
            return
        if isinstance(record, Payment) and record.is_reversed:
            QMessageBox.information(self, "Reversed", "Cannot generate a reversed receipt.")
            return
        try:
            invoice = record.invoice if isinstance(record, Payment) else None
            if isinstance(record, Payment):
                record.receipt_number = record.receipt_number or self._context.payment_service._numbering.reserve("receipt")
                self._context.payment_service._persist_numbering()
                number = record.receipt_number
            else:
                number = record.number
            path = (
                self._context.config.get_documents_directory()
                / "receipts"
                / str(cast(date, record.date).year)
                / f"{number}.{extension}"
            )
            settings = _receipt_settings(self._context)
            if extension == "pdf":
                generate_receipt_pdf(record, invoice, settings, path)
                record.pdf_path = str(path)
            elif extension == "docx":
                generate_receipt_docx(record, invoice, settings, path)
                if isinstance(record, Receipt):
                    record.docx_path = str(path)
            else:
                generate_receipt_xlsx(record, invoice, settings, path)
                if isinstance(record, Receipt):
                    record.xlsx_path = str(path)
            self._context.session.commit()
            self.refresh()
            os.startfile(str(path))
        except Exception as exc:  # noqa: BLE001
            self._context.session.rollback()
            QMessageBox.warning(self, "Receipt failed", str(exc))

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
