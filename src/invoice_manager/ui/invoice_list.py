"""Invoice list page."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.documents.invoice_pdf import generate_invoice_pdf
from invoice_manager.persistence.models import Invoice
from invoice_manager.ui.app_context import AppContext
from invoice_manager.ui.invoice_editor import InvoiceEditorDialog
from invoice_manager.ui.manual_invoice_dialog import ManualInvoiceDialog


class InvoiceListPage(QWidget):
    """Page showing issued invoices with actions."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._invoices: list[Invoice] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Invoices"))

        toolbar = QHBoxLayout()
        new_btn = QPushButton("New Invoice")
        new_btn.clicked.connect(self._new_invoice)
        manual_btn = QPushButton("Record Manual Invoice")
        manual_btn.clicked.connect(self._record_manual)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(new_btn)
        toolbar.addWidget(manual_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["Number", "Date", "Due", "Client", "Total", "Balance", "Status", "PDF"]
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        action_bar = QHBoxLayout()
        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.clicked.connect(self._open_pdf)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._cancel_invoice)
        void_btn = QPushButton("Void")
        void_btn.clicked.connect(self._void_invoice)
        regen_btn = QPushButton("Regenerate PDF")
        regen_btn.clicked.connect(self._regenerate_pdf)
        action_bar.addWidget(open_pdf_btn)
        action_bar.addWidget(cancel_btn)
        action_bar.addWidget(void_btn)
        action_bar.addWidget(regen_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def refresh(self) -> None:
        self._invoices = list(self._context.invoice_service.list_invoices())
        self._table.setRowCount(len(self._invoices))
        for row, inv in enumerate(self._invoices):
            self._table.setItem(row, 0, QTableWidgetItem(inv.number))
            self._table.setItem(row, 1, QTableWidgetItem(str(inv.issue_date)))
            self._table.setItem(row, 2, QTableWidgetItem(str(inv.due_date or "")))
            self._table.setItem(row, 3, QTableWidgetItem(inv.client_name))
            self._table.setItem(row, 4, QTableWidgetItem(f"${inv.total_cents / 100:.2f}"))
            balance = inv.total_cents - sum(
                p.amount_cents for p in inv.payments if not p.is_reversed
            )
            self._table.setItem(row, 5, QTableWidgetItem(f"${balance / 100:.2f}"))
            status_item = QTableWidgetItem(inv.status)
            status_item.setData(Qt.ItemDataRole.UserRole, inv.id)
            self._table.setItem(row, 6, status_item)
            self._table.setItem(row, 7, QTableWidgetItem("Yes" if inv.pdf_path else "No"))

    def _selected_invoice(self) -> Invoice | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        row = rows[0].row()
        return self._invoices[row]

    def _open_pdf(self) -> None:
        inv = self._selected_invoice()
        if inv is None or not inv.pdf_path:
            QMessageBox.information(self, "No PDF", "Select an invoice that has a PDF.")
            return
        path = Path(inv.pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Missing", f"PDF not found: {path}")
            return
        import os

        os.startfile(str(path))

    def _new_invoice(self) -> None:
        dlg = InvoiceEditorDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _record_manual(self) -> None:
        dlg = ManualInvoiceDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _cancel_invoice(self) -> None:
        inv = self._selected_invoice()
        if inv is None:
            QMessageBox.information(self, "Select invoice", "Select an invoice to cancel.")
            return
        if inv.is_cancelled or inv.is_void or inv.is_draft:
            QMessageBox.information(self, "Cannot cancel", "Invoice is already cancelled, void, or a draft.")
            return
        reason, ok = QInputDialog.getText(self, "Cancel Invoice", "Reason for cancellation:")
        if not ok or not reason.strip():
            return
        try:
            self._context.invoice_service.cancel(inv, reason.strip())
            self._context.session.commit()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Cancel failed", str(exc))

    def _void_invoice(self) -> None:
        inv = self._selected_invoice()
        if inv is None:
            QMessageBox.information(self, "Select invoice", "Select an invoice to void.")
            return
        if inv.is_void or inv.is_cancelled or inv.is_draft:
            QMessageBox.information(self, "Cannot void", "Invoice is already void, cancelled, or a draft.")
            return
        reason, ok = QInputDialog.getText(self, "Void Invoice", "Reason for voiding:")
        if not ok or not reason.strip():
            return
        try:
            self._context.invoice_service.void(inv, reason.strip())
            self._context.session.commit()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Void failed", str(exc))

    def _regenerate_pdf(self) -> None:
        inv = self._selected_invoice()
        if inv is None:
            QMessageBox.information(self, "Select invoice", "Select an invoice.")
            return
        if inv.is_draft:
            QMessageBox.information(self, "Not issued", "Draft invoices do not have a PDF.")
            return
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
                / str(cast(date, inv.issue_date).year)
                / f"{inv.number}.pdf"
            )
            generate_invoice_pdf(inv, settings, pdf_path)
            inv.pdf_path = str(pdf_path)
            self._context.session.commit()
            QMessageBox.information(self, "PDF regenerated", f"Saved {pdf_path}")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "PDF failed", str(exc))
