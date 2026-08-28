"""Generate an Excel workbook version of an invoice."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from invoice_manager.domain.money import Money
from invoice_manager.persistence.models import Invoice


def _get(settings: dict[str, Any], key: str, default: str = "") -> str:
    value = settings.get(key, default)
    if not value:
        return default
    return str(value)


def _fmt(cents: int) -> str:
    return Money(cents=cents).__str__()


def generate_invoice_xlsx(invoice: Invoice, settings: dict[str, Any], output_path: Path) -> Path:
    """Create an .xlsx workbook for the invoice."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        sheet = workbook.create_sheet("Invoice")
    sheet.title = invoice.number

    header_fill = PatternFill("solid", fgColor="2C3E50")
    header_font = Font(color="FFFFFF", bold=True)

    row = 1
    sheet.cell(row=row, column=1, value=_get(settings, "business_name", "Invoice"))
    sheet.cell(row=row, column=1).font = Font(bold=True, size=14)
    row += 1
    if _get(settings, "business_address"):
        sheet.cell(row=row, column=1, value=_get(settings, "business_address"))
        row += 1
    row += 1

    gst_rate = Decimal(_get(settings, "gst_rate", "0.0") or "0.0")
    doc_title = (
        _get(settings, "invoice_title_tax", "TAX INVOICE")
        if gst_rate > 0
        else _get(settings, "invoice_title", "INVOICE")
    )
    sheet.cell(row=row, column=1, value=f"{doc_title} — {invoice.number}")
    sheet.cell(row=row, column=1).font = Font(bold=True, size=12)
    row += 1
    row += 1

    meta = [
        (_get(settings, "invoice_date_label", "Date:"), str(invoice.issue_date)),
        (_get(settings, "invoice_due_date_label", "Due date:"), str(invoice.due_date or "")),
        (_get(settings, "invoice_client_label", "Client:"), invoice.client_name),
        (_get(settings, "invoice_address_label", "Address:"), invoice.client_address or ""),
    ]
    for label, value in meta:
        sheet.cell(row=row, column=1, value=label)
        sheet.cell(row=row, column=1).font = Font(bold=True)
        sheet.cell(row=row, column=2, value=value)
        row += 1
    row += 1

    headers = [
        _get(settings, "invoice_description_header", "Description"),
        _get(settings, "invoice_qty_header", "Qty"),
        _get(settings, "invoice_unit_header", "Unit"),
        _get(settings, "invoice_price_header", "Price"),
        _get(settings, "invoice_gst_header", "GST"),
        _get(settings, "invoice_total_header", "Total"),
    ]
    for col, header in enumerate(headers, 1):
        cell = sheet.cell(row=row, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    row += 1

    for item in invoice.items:
        sheet.cell(row=row, column=1, value=item.description)
        sheet.cell(row=row, column=2, value=item.quantity)
        sheet.cell(row=row, column=3, value=item.unit or "ea")
        sheet.cell(row=row, column=4, value=_fmt(item.unit_price_cents))
        sheet.cell(row=row, column=5, value=_fmt(item.gst_cents))
        sheet.cell(row=row, column=6, value=_fmt(item.total_cents))
        row += 1

    summary = [
        (3, _get(settings, "invoice_subtotal_label", "Subtotal"), _fmt(invoice.subtotal_cents)),
        (3, _get(settings, "invoice_gst_label", "GST"), _fmt(invoice.gst_cents)),
        (3, _get(settings, "invoice_total_label", "Total"), _fmt(invoice.total_cents)),
    ]
    for col, label, value in summary:
        sheet.cell(row=row, column=col, value=label)
        sheet.cell(row=row, column=col).font = Font(bold=True)
        sheet.cell(row=row, column=col + 3, value=value)
        sheet.cell(row=row, column=col + 3).font = Font(bold=True)
        row += 1
    row += 1

    bank_name = _get(settings, "bank_name")
    bsb = _get(settings, "bank_bsb")
    account = _get(settings, "bank_account")
    account_name = _get(settings, "bank_account_name")
    if bank_name or account:
        sheet.cell(row=row, column=1, value=_get(settings, "invoice_payment_details_label", "Payment details"))
        sheet.cell(row=row, column=1).font = Font(bold=True)
        row += 1
        payment_line = (
            f"{_get(settings, 'invoice_bank_label', 'Bank:')} {bank_name}  |  "
            f"{_get(settings, 'invoice_bsb_label', 'BSB:')} {bsb}  |  "
            f"{_get(settings, 'invoice_account_label', 'Account:')} {account}  |  "
            f"{_get(settings, 'invoice_account_name_label', 'Name:')} {account_name}"
        )
        sheet.cell(row=row, column=1, value=payment_line)
        row += 1
        row += 1

    if invoice.notes:
        sheet.cell(row=row, column=1, value=f"{_get(settings, 'invoice_notes_label', 'Notes:')} {invoice.notes}")
        row += 1

    thank_you = _get(settings, "invoice_thank_you", "Thank you for your business!")
    if thank_you:
        sheet.cell(row=row, column=1, value=thank_you)
        row += 1

    for col in range(1, 7):
        sheet.column_dimensions[chr(64 + col)].auto_size = True

    workbook.save(output_path)
    return output_path
