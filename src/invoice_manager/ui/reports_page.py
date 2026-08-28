"""Reports page with multiple report tabs."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.documents.invoice_pdf import generate_report_pdf
from invoice_manager.persistence.models import AuditLog, Invoice, LedgerEntry
from invoice_manager.ui.app_context import AppContext


def _fmt_cents(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _parse_gst_rate(raw: str | None) -> Decimal:
    try:
        return Decimal(raw or "0.0")
    except Exception:
        return Decimal("0.0")


def _qdate_to_date(qdate: QDate) -> date:
    return cast(date, qdate.toPython())


class ReportsPage(QWidget):
    """Page containing several report tabs."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Reports"))
        tabs = QTabWidget()
        tabs.addTab(SummaryTab(self._context), "Summary")
        tabs.addTab(InvoicesTab(self._context), "Invoices")
        tabs.addTab(LedgerTab(self._context), "Ledger")
        tabs.addTab(GSTTab(self._context), "GST")
        tabs.addTab(AgeingTab(self._context), "Ageing")
        tabs.addTab(AuditTab(self._context), "Audit Log")
        tabs.addTab(AppLogTab(self._context), "Application Log")
        layout.addWidget(tabs)


class _BaseReportTab(QWidget):
    """Base class for report tabs with a refresh/export toolbar."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context

    def _export_csv(
        self,
        default_name: str,
        headers: list[str],
        rows: list[list[Any]],
    ) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            str(self._context.config.get_exports_directory() / default_name),
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with Path(path).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row)
            self._context.audit.record(
                "report_exported", "reports", None, {"path": path, "format": "csv"}
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))

    def _add_toolbar(
        self,
        layout: QVBoxLayout,
        refresh_fn: Callable[[], None],
        export_fn: Callable[[], None],
    ) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(refresh_fn)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(export_fn)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        return toolbar

    @staticmethod
    def _table_rows(table: QTableWidget) -> list[list[str]]:
        rows: list[list[str]] = []
        for r in range(table.rowCount()):
            row: list[str] = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        return rows


class SummaryTab(_BaseReportTab):
    """Summary of invoices, ledger and GST."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self._generate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._generate)
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self._export_csv_summary)
        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.clicked.connect(self._export_pdf_summary)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(export_csv_btn)
        toolbar.addWidget(export_pdf_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output)

    def _generate(self) -> None:
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
            lines.append(f"{status}: {_fmt_cents(cents)}")
        lines.append(f"Total issued: {_fmt_cents(total_invoiced)}")
        lines.append(f"Total outstanding: {_fmt_cents(total_outstanding)}")
        return lines

    def _ledger_summary(self) -> list[str]:
        entries = (
            self._context.session.query(LedgerEntry)
            .filter(LedgerEntry.is_deleted.is_(False))
            .all()
        )
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
            lines.append(f"{category}: {_fmt_cents(cents)}")
        lines.append(f"This month income: {_fmt_cents(month_income)}")
        lines.append(f"This month expenses: {_fmt_cents(month_expense)}")
        return lines

    def _gst_summary(self) -> list[str]:
        gst_collected = 0
        total_sales = 0
        for inv in self._context.session.query(Invoice).all():
            if inv.is_void or inv.is_cancelled or inv.is_draft:
                continue
            gst_collected += inv.gst_cents
            total_sales += inv.total_cents

        expenses = sum(
            e.amount_cents
            for e in self._context.session.query(LedgerEntry)
            .filter(LedgerEntry.is_deleted.is_(False), LedgerEntry.entry_type == "out")
            .all()
        )
        rate = _parse_gst_rate(self._context.setting_repo.get("gst_rate"))
        if rate > 0:
            gst_paid = (
                (Decimal(expenses) / Decimal(100)) * rate / (Decimal(1) + rate)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gst_paid_cents = int(gst_paid * Decimal(100))
        else:
            gst_paid_cents = 0

        lines = ["GST Summary", "-" * 20]
        lines.append(f"Total sales (incl. GST): {_fmt_cents(total_sales)}")
        lines.append(f"GST collected: {_fmt_cents(gst_collected)}")
        lines.append(f"Total expenses: {_fmt_cents(expenses)}")
        lines.append(f"Estimated GST paid/credits: {_fmt_cents(gst_paid_cents)}")
        lines.append(f"Net GST position: {_fmt_cents(gst_collected - gst_paid_cents)}")
        return lines

    def _export_csv_summary(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export report CSV",
            str(self._context.config.get_exports_directory() / "report_summary.csv"),
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with Path(path).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for line in self._output.toPlainText().splitlines():
                    if ":" in line:
                        label, value = line.split(":", 1)
                        writer.writerow([label.strip(), value.strip()])
                    else:
                        writer.writerow([line])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))

    def _export_pdf_summary(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export report PDF",
            str(self._context.config.get_exports_directory() / "report_summary.pdf"),
            "PDF files (*.pdf)",
        )
        if not path:
            return
        try:
            generate_report_pdf(
                "Business Report", self._output.toPlainText().splitlines(), Path(path)
            )
            self._context.audit.record(
                "report_exported", "reports", None, {"path": path, "format": "pdf"}
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))


class InvoicesTab(_BaseReportTab):
    """Filterable invoice report."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filter_bar = QHBoxLayout()
        self._status_filter = QComboBox()
        self._status_filter.addItems(["All", "Issued", "Paid", "Part paid", "Overdue", "Draft", "Cancelled", "Void"])
        self._status_filter.currentTextChanged.connect(self.refresh)
        self._client_filter = QLineEdit()
        self._client_filter.setPlaceholderText("Client name...")
        self._client_filter.textChanged.connect(self.refresh)
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setSpecialValueText("From")
        self._from_date.setDate(self._from_date.minimumDate())
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setSpecialValueText("To")
        self._to_date.setDate(self._to_date.maximumDate())
        self._from_date.dateChanged.connect(self.refresh)
        self._to_date.dateChanged.connect(self.refresh)
        filter_bar.addWidget(QLabel("Status:"))
        filter_bar.addWidget(self._status_filter)
        filter_bar.addWidget(QLabel("Client:"))
        filter_bar.addWidget(self._client_filter)
        filter_bar.addWidget(QLabel("From:"))
        filter_bar.addWidget(self._from_date)
        filter_bar.addWidget(QLabel("To:"))
        filter_bar.addWidget(self._to_date)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)
        self._add_toolbar(layout, self.refresh, self._export)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["Number", "Date", "Due", "Client", "Total", "Paid", "Balance", "Status"]
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        status = self._status_filter.currentText().lower()
        client = self._client_filter.text().strip().lower()
        q_from = _qdate_to_date(self._from_date.date())
        q_to = _qdate_to_date(self._to_date.date())

        invoices = self._context.session.query(Invoice).order_by(Invoice.issue_date.desc()).all()
        rows: list[list[Any]] = []
        today = date.today()
        for inv in invoices:
            if client and client not in inv.client_name.lower():
                continue
            issue_date = cast(date, inv.issue_date)
            if not self._date_in_range(issue_date, q_from, q_to):
                continue
            if status != "all":
                if status == "overdue":
                    if inv.is_draft or inv.is_cancelled or inv.is_void:
                        continue
                    paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
                    balance = inv.total_cents - paid
                    if balance <= 0:
                        continue
                    due = inv.due_date
                    if due is None or cast(date, due) >= today:
                        continue
                elif status == "issued":
                    if inv.is_draft or inv.is_cancelled or inv.is_void:
                        continue
                elif inv.status != status:
                    continue

            paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
            balance = inv.total_cents - paid
            rows.append(
                [
                    inv.number,
                    inv.issue_date,
                    inv.due_date or "",
                    inv.client_name,
                    _fmt_cents(inv.total_cents),
                    _fmt_cents(paid),
                    _fmt_cents(balance),
                    inv.status,
                ]
            )

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _date_in_range(self, py_date: date, q_from: date, q_to: date) -> bool:
        min_from = _qdate_to_date(self._from_date.minimumDate())
        max_to = _qdate_to_date(self._to_date.maximumDate())
        return not (
            (q_from != min_from and py_date < q_from) or (q_to != max_to and py_date > q_to)
        )

    def _export(self) -> None:
        headers = ["Number", "Date", "Due", "Client", "Total", "Paid", "Balance", "Status"]
        self._export_csv("report_invoices.csv", headers, self._table_rows(self._table))


class LedgerTab(_BaseReportTab):
    """Filterable ledger report."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filter_bar = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.addItems(["All", "Income", "Expense"])
        self._type_filter.currentTextChanged.connect(self.refresh)
        self._category_filter = QComboBox()
        self._category_filter.setEditable(False)
        self._category_filter.addItem("All")
        self._category_filter.currentTextChanged.connect(self.refresh)
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setSpecialValueText("From")
        self._from_date.setDate(self._from_date.minimumDate())
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setSpecialValueText("To")
        self._to_date.setDate(self._to_date.maximumDate())
        self._from_date.dateChanged.connect(self.refresh)
        self._to_date.dateChanged.connect(self.refresh)
        filter_bar.addWidget(QLabel("Type:"))
        filter_bar.addWidget(self._type_filter)
        filter_bar.addWidget(QLabel("Category:"))
        filter_bar.addWidget(self._category_filter)
        filter_bar.addWidget(QLabel("From:"))
        filter_bar.addWidget(self._from_date)
        filter_bar.addWidget(QLabel("To:"))
        filter_bar.addWidget(self._to_date)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)
        self._add_toolbar(layout, self.refresh, self._export)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Date", "Type", "Category", "Description", "Amount", "Reference"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        selected_type = self._type_filter.currentText().lower()
        selected_category = self._category_filter.currentText()
        q_from = _qdate_to_date(self._from_date.date())
        q_to = _qdate_to_date(self._to_date.date())
        entries = (
            self._context.session.query(LedgerEntry)
            .filter(LedgerEntry.is_deleted.is_(False))
            .order_by(LedgerEntry.date.desc())
            .all()
        )

        categories = sorted({e.category for e in entries})
        current = self._category_filter.currentText()
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("All")
        self._category_filter.addItems(categories)
        if current in categories or current == "All":
            self._category_filter.setCurrentText(current)
        self._category_filter.blockSignals(False)

        rows: list[list[Any]] = []
        for entry in entries:
            if selected_type != "all" and (
                (selected_type == "income" and entry.entry_type != "in")
                or (selected_type == "expense" and entry.entry_type != "out")
            ):
                continue
            if selected_category != "All" and entry.category != selected_category:
                continue
            entry_date = cast(date, entry.date)
            if not self._date_in_range(entry_date, q_from, q_to):
                continue
            rows.append(
                [
                    entry.date,
                    entry.entry_type.upper(),
                    entry.category,
                    entry.description,
                    _fmt_cents(entry.amount_cents),
                    entry.reference or "",
                ]
            )

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _date_in_range(self, py_date: date, q_from: date, q_to: date) -> bool:
        min_from = _qdate_to_date(self._from_date.minimumDate())
        max_to = _qdate_to_date(self._to_date.maximumDate())
        return not (
            (q_from != min_from and py_date < q_from) or (q_to != max_to and py_date > q_to)
        )

    def _export(self) -> None:
        headers = ["Date", "Type", "Category", "Description", "Amount", "Reference"]
        self._export_csv("report_ledger.csv", headers, self._table_rows(self._table))


class GSTTab(_BaseReportTab):
    """GST collected vs paid/estimated credits."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._add_toolbar(layout, self.refresh, self._export)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Item", "Amount"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        gst_collected = 0
        total_sales = 0
        for inv in self._context.session.query(Invoice).all():
            if inv.is_void or inv.is_cancelled or inv.is_draft:
                continue
            gst_collected += inv.gst_cents
            total_sales += inv.total_cents

        expenses = sum(
            e.amount_cents
            for e in self._context.session.query(LedgerEntry)
            .filter(LedgerEntry.is_deleted.is_(False), LedgerEntry.entry_type == "out")
            .all()
        )
        rate = _parse_gst_rate(self._context.setting_repo.get("gst_rate"))
        if rate > 0:
            gst_paid = (
                (Decimal(expenses) / Decimal(100)) * rate / (Decimal(1) + rate)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gst_paid_cents = int(gst_paid * Decimal(100))
        else:
            gst_paid_cents = 0

        self._rows: list[list[Any]] = [
            ["Total sales (incl. GST)", _fmt_cents(total_sales)],
            ["GST collected", _fmt_cents(gst_collected)],
            ["Total expenses", _fmt_cents(expenses)],
            ["Estimated GST paid/credits", _fmt_cents(gst_paid_cents)],
            ["Net GST position", _fmt_cents(gst_collected - gst_paid_cents)],
        ]
        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _export(self) -> None:
        self._export_csv("report_gst.csv", ["Item", "Amount"], self._table_rows(self._table))


class AgeingTab(_BaseReportTab):
    """Invoice ageing report."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._add_toolbar(layout, self.refresh, self._export)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Bucket", "Invoices", "Balance", "%"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        today = date.today()
        buckets: dict[str, int] = {
            "Current": 0,
            "1-30 days": 0,
            "31-60 days": 0,
            "61-90 days": 0,
            "90+ days": 0,
        }
        counts: dict[str, int] = {k: 0 for k in buckets}
        for inv in self._context.session.query(Invoice).all():
            if inv.is_draft or inv.is_cancelled or inv.is_void:
                continue
            paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
            balance = inv.total_cents - paid
            if balance <= 0:
                continue
            due = inv.due_date
            days = 0 if due is None else (today - cast(date, due)).days
            if days <= 0:
                bucket = "Current"
            elif days <= 30:
                bucket = "1-30 days"
            elif days <= 60:
                bucket = "31-60 days"
            elif days <= 90:
                bucket = "61-90 days"
            else:
                bucket = "90+ days"
            buckets[bucket] += balance
            counts[bucket] += 1

        total = sum(buckets.values()) or 1
        self._rows: list[list[Any]] = []
        for bucket in ["Current", "1-30 days", "31-60 days", "61-90 days", "90+ days"]:
            self._rows.append(
                [bucket, counts[bucket], _fmt_cents(buckets[bucket]), f"{buckets[bucket] / total * 100:.1f}%"]
            )
        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _export(self) -> None:
        self._export_csv("report_ageing.csv", ["Bucket", "Invoices", "Balance", "%"], self._table_rows(self._table))


class AuditTab(_BaseReportTab):
    """Audit log viewer."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filter_bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search actions, tables, users...")
        self._search.textChanged.connect(self.refresh)
        filter_bar.addWidget(QLabel("Search:"))
        filter_bar.addWidget(self._search)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)
        self._add_toolbar(layout, self.refresh, self._export)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Time", "User", "Action", "Table", "Detail"])
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        query = self._context.session.query(AuditLog).order_by(AuditLog.timestamp.desc())
        text = self._search.text().strip().lower()
        logs = query.limit(1000).all()
        rows: list[list[Any]] = []
        for log in logs:
            detail = log.detail or ""
            if text:
                searchable = f"{log.action} {log.table_name or ''} {log.user} {detail}".lower()
                if text not in searchable:
                    continue
            rows.append(
                [
                    str(log.timestamp)[:19],
                    log.user,
                    log.action,
                    log.table_name or "",
                    detail[:120],
                ]
            )
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _export(self) -> None:
        headers = ["Time", "User", "Action", "Table", "Detail"]
        self._export_csv("report_audit.csv", headers, self._table_rows(self._table))


class AppLogTab(_BaseReportTab):
    """Application log viewer."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filter_bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter log lines...")
        self._search.textChanged.connect(self._apply_filter)
        filter_bar.addWidget(QLabel("Filter:"))
        filter_bar.addWidget(self._search)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output)

    def refresh(self) -> None:
        log_path = self._context.config.get_logs_directory() / "application.log"
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except FileNotFoundError:
            text = "No application log found."
        self._full_text = text
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().strip().lower()
        if not text:
            self._output.setPlainText(self._full_text)
            return
        lines = [line for line in self._full_text.splitlines() if text in line.lower()]
        self._output.setPlainText("\n".join(lines))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export application log",
            str(self._context.config.get_exports_directory() / "application_log.txt"),
            "Text files (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._output.toPlainText(), encoding="utf-8")
            self._context.audit.record(
                "report_exported", "reports", None, {"path": path, "format": "txt"}
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))
