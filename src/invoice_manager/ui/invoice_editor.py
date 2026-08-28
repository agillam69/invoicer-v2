"""Dialog for creating a new invoice."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.documents.invoice_pdf import generate_invoice_pdf
from invoice_manager.domain.invoices import calculate_line_total
from invoice_manager.persistence.models import Client, Invoice
from invoice_manager.ui.app_context import AppContext


class InvoiceEditorDialog(QDialog):
    """Create and optionally issue a new invoice."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("New Invoice")
        self.setMinimumSize(700, 500)
        self._invoice: Invoice | None = None
        self._clients: list[Client] = []
        self._build_ui()
        self._load_clients()
        self._load_services()
        self._table.itemChanged.connect(self._recalc)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._client = QComboBox()
        self._client.setEditable(False)
        form.addRow("Client:", self._client)

        self._issue_date = QDateEdit()
        self._issue_date.setCalendarPopup(True)
        self._issue_date.setDate(QDate.currentDate())
        form.addRow("Invoice date:", self._issue_date)

        self._due_date = QDateEdit()
        self._due_date.setCalendarPopup(True)
        self._due_date.setDate(QDate.currentDate())
        form.addRow("Due date:", self._due_date)

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)
        form.addRow("Notes:", self._notes)

        service_widget = QWidget()
        service_layout = QHBoxLayout(service_widget)
        service_layout.setContentsMargins(0, 0, 0, 0)
        self._service_combo = QComboBox()
        self._service_combo.addItem("-- select a service --", 0)
        service_layout.addWidget(self._service_combo, stretch=1)
        add_service_btn = QPushButton("Add to invoice")
        add_service_btn.clicked.connect(self._add_service_line)
        service_layout.addWidget(add_service_btn)
        form.addRow("Service:", service_widget)

        layout.addLayout(form)

        layout.addWidget(QLabel("Line items"))
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Description", "Qty", "Price", "Taxable", "Discount", "Total"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add line")
        add_btn.clicked.connect(self._add_line)
        del_btn = QPushButton("Remove line")
        del_btn.clicked.connect(self._remove_line)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        totals = QHBoxLayout()
        self._subtotal_lbl = QLabel("Subtotal: $0.00")
        self._gst_lbl = QLabel("GST: $0.00")
        self._total_lbl = QLabel("Total: $0.00")
        totals.addWidget(self._subtotal_lbl)
        totals.addWidget(self._gst_lbl)
        totals.addWidget(self._total_lbl)
        totals.addStretch()
        layout.addLayout(totals)

        bbox = QDialogButtonBox()
        self._save_draft_btn = bbox.addButton("Save Draft", QDialogButtonBox.ButtonRole.ActionRole)
        self._issue_btn = bbox.addButton("Issue", QDialogButtonBox.ButtonRole.ActionRole)
        bbox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bbox.rejected.connect(self.reject)
        self._save_draft_btn.clicked.connect(self._save_draft)
        self._issue_btn.clicked.connect(self._issue)
        layout.addWidget(bbox)

        self._add_line()

    def _load_clients(self) -> None:
        self._clients = self._context.client_repo.list_active()
        for client in self._clients:
            self._client.addItem(client.name, client.id)
        if self._clients:
            self._client.setCurrentIndex(0)
            self._update_due_date()
        self._issue_date.dateChanged.connect(self._update_due_date)

    def _load_services(self) -> None:
        for item in self._context.service_repo.list_active():
            self._service_combo.addItem(item.description, item.id)

    def _update_due_date(self) -> None:
        terms = int(self._context.setting_repo.get("payment_terms_days") or 7)
        self._due_date.setDate(self._issue_date.date().addDays(terms))

    def _add_line(
        self,
        description: str = "Service",
        quantity: int = 1,
        unit_price_cents: int = 0,
        taxable: bool = True,
    ) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(description))
        self._table.setItem(row, 1, QTableWidgetItem(str(quantity)))
        self._table.setItem(row, 2, QTableWidgetItem(f"{unit_price_cents / 100:.2f}"))
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk.setCheckState(Qt.CheckState.Checked if taxable else Qt.CheckState.Unchecked)
        self._table.setItem(row, 3, chk)
        self._table.setItem(row, 4, QTableWidgetItem("0.00"))
        self._table.setItem(row, 5, QTableWidgetItem("$0.00"))
        self._recalc()

    def _add_service_line(self) -> None:
        service_id = self._service_combo.currentData()
        if service_id is None or service_id == 0:
            return
        item = self._context.service_repo.get(int(service_id))
        if item is None:
            return
        self._add_line(
            description=item.description,
            quantity=1,
            unit_price_cents=item.unit_price_cents,
            taxable=item.taxable,
        )
        self._service_combo.setCurrentIndex(0)

    def _remove_line(self) -> None:
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)
        self._recalc()

    def _recalc(self) -> None:
        gst_rate = Decimal(self._context.setting_repo.get("gst_rate") or "0.0")
        subtotal = 0
        gst = 0
        total = 0
        for row in range(self._table.rowCount()):
            qty = self._int_at(row, 1, 1)
            price = self._cents_at(row, 2)
            discount = self._cents_at(row, 4)
            taxable = self._item_check(row, 3)
            s, g, t = calculate_line_total(qty, price, discount, taxable, gst_rate)
            self._set_item_text(row, 5, f"${t / 100:.2f}")
            subtotal += s
            gst += g
            total += t
        self._subtotal_lbl.setText(f"Subtotal: ${subtotal / 100:.2f}")
        self._gst_lbl.setText(f"GST: ${gst / 100:.2f}")
        self._total_lbl.setText(f"Total: ${total / 100:.2f}")

    def _int_at(self, row: int, col: int, default: int) -> int:
        try:
            return int(self._item_text(row, col) or default)
        except (ValueError, AttributeError):
            return default

    def _cents_at(self, row: int, col: int) -> int:
        try:
            return int(Decimal(self._item_text(row, col) or "0") * 100)
        except Exception:
            return 0

    def _item_text(self, row: int, col: int, default: str = "") -> str:
        item = self._table.item(row, col)
        return item.text() if item is not None else default

    def _item_check(self, row: int, col: int) -> bool:
        item = self._table.item(row, col)
        return item.checkState() == Qt.CheckState.Checked if item is not None else False

    def _set_item_text(self, row: int, col: int, text: str) -> None:
        item = self._table.item(row, col)
        if item is not None:
            item.setText(text)

    def _collect_lines(self) -> list[dict[str, Any]]:
        lines = []
        for row in range(self._table.rowCount()):
            lines.append(
                {
                    "description": self._item_text(row, 0) or "Item",
                    "quantity": self._int_at(row, 1, 1),
                    "unit_price_cents": self._cents_at(row, 2),
                    "discount_cents": self._cents_at(row, 4),
                    "taxable": self._item_check(row, 3),
                }
            )
        return lines

    def _create_invoice(self) -> Invoice | None:
        client_id = self._client.currentData()
        if client_id is None:
            QMessageBox.warning(self, "No client", "Please select a client.")
            return None
        lines = self._collect_lines()
        if not lines or all(line["unit_price_cents"] == 0 for line in lines):
            QMessageBox.warning(self, "No lines", "Add at least one priced line item.")
            return None
        invoice = self._context.invoice_service.create_draft(
            client_id=int(client_id),
            invoice_date=cast(date, self._issue_date.date().toPython()),
            due_date=cast(date, self._due_date.date().toPython()),
            notes=self._notes.toPlainText().strip() or None,
        )
        for line in lines:
            self._context.invoice_service.add_line(
                invoice,
                line["description"],
                line["quantity"],
                line["unit_price_cents"],
                line["taxable"],
                line["discount_cents"],
            )
        return invoice

    def _save_draft(self) -> None:
        self._invoice = self._create_invoice()
        if self._invoice:
            self._context.session.commit()
            QMessageBox.information(self, "Draft saved", f"Saved draft ID {self._invoice.id}")
            self.accept()

    def _issue(self) -> None:
        invoice = self._create_invoice()
        if invoice is None:
            return
        self._context.invoice_service.issue(invoice)
        self._context.session.commit()
        try:
            settings = {
                k: self._context.setting_repo.get(k)
                for k in [
                    "business_name",
                    "business_address",
                    "gst_rate",
                    "bank_name",
                    "bank_bsb",
                    "bank_account",
                    "bank_account_name",
                    "thank_you_note",
                ]
            }
            pdf_path = (
                self._context.config.get_data_directory()
                / "documents"
                / "invoices"
                / str(cast(date, invoice.issue_date).year)
                / f"{invoice.number}.pdf"
            )
            generate_invoice_pdf(invoice, settings, pdf_path)
            invoice.pdf_path = str(pdf_path)
            self._context.session.commit()
            QMessageBox.information(
                self, "Issued", f"Invoice {invoice.number} issued and PDF saved."
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "PDF failed", str(exc))
        self._invoice = invoice
        self.accept()
