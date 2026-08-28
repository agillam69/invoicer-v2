"""Reports page."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import cast

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.persistence.models import Invoice, LedgerEntry
from invoice_manager.ui.app_context import AppContext


class ReportsPage(QWidget):
    """Page showing simple financial reports."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._build_ui()
        self._generate_all()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Reports"))

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._generate_all)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output)

    def _generate_all(self) -> None:
        lines: list[str] = []
        lines.extend(self._invoice_summary())
        lines.append("")
        lines.extend(self._ledger_summary())
        lines.append("")
        lines.extend(self._gst_summary())
        self._output.setPlainText("\n".join(lines))

    def _invoice_summary(self) -> list[str]:
        session = self._context.session
        invoices = session.query(Invoice).all()
        by_status: dict[str, int] = defaultdict(int)
        total_invoiced = 0
        total_outstanding = 0
        for inv in invoices:
            if inv.is_void or inv.is_cancelled or inv.is_draft:
                continue
            by_status[inv.status] += inv.total_cents
            total_invoiced += inv.total_cents
            paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
            total_outstanding += inv.total_cents - paid

        lines = ["Invoice Summary", "-" * 20]
        for status, cents in sorted(by_status.items()):
            lines.append(f"{status}: ${cents / 100:.2f}")
        lines.append(f"Total issued: ${total_invoiced / 100:.2f}")
        lines.append(f"Total outstanding: ${total_outstanding / 100:.2f}")
        return lines

    def _ledger_summary(self) -> list[str]:
        session = self._context.session
        entries = session.query(LedgerEntry).filter(LedgerEntry.is_deleted.is_(False)).all()
        by_category: dict[str, int] = defaultdict(int)
        month_income = 0
        month_expense = 0
        today = date.today()
        for entry in entries:
            entry_date = cast(date, entry.date)
            if entry.entry_type == "out":
                by_category[entry.category] -= entry.amount_cents
            else:
                by_category[entry.category] += entry.amount_cents
            if entry_date.month == today.month and entry_date.year == today.year:
                if entry.entry_type == "in":
                    month_income += entry.amount_cents
                else:
                    month_expense += entry.amount_cents

        lines = ["Ledger Summary", "-" * 20]
        for category, cents in sorted(by_category.items()):
            lines.append(f"{category}: ${cents / 100:.2f}")
        lines.append(f"This month income: ${month_income / 100:.2f}")
        lines.append(f"This month expenses: ${month_expense / 100:.2f}")
        return lines

    def _gst_summary(self) -> list[str]:
        session = self._context.session
        invoices = session.query(Invoice).all()
        gst_collected = 0
        for inv in invoices:
            if inv.is_void or inv.is_cancelled or inv.is_draft:
                continue
            gst_collected += inv.gst_cents
        # GST on expenses from ledger (items marked taxable? not stored yet)
        # Placeholder for future expense-GST tracking.
        lines = ["GST Summary", "-" * 20]
        lines.append(f"GST collected (invoices): ${gst_collected / 100:.2f}")
        lines.append("GST paid (expenses): not yet tracked")
        return lines
