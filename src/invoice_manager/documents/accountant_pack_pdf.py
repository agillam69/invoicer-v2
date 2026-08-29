"""Accountant report pack PDF builder.

Produces a single PDF containing:
- Cover page
- Profit & Loss summary
- Invoice list
- Ledger income detail
- Ledger expense detail
- ATO / BAS summary
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, cast

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select

from invoice_manager.domain.money import format_money
from invoice_manager.domain.tax_year import TaxYear
from invoice_manager.persistence.models import Invoice, LedgerEntry
from invoice_manager.ui.app_context import AppContext


def _fmt_cents(cents: int, symbol: str = "$") -> str:
    return format_money(cents, symbol=symbol)


def _hex_color(value: str, default: str) -> colors.HexColor:
    try:
        return colors.HexColor(value)
    except Exception:
        return colors.HexColor(default)


def _make_styles(header_colour: colors.HexColor) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]

    def _style(name: str, **kwargs: Any) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base, **kwargs)

    return {
        "h1": _style("h1", fontSize=22, fontName="Helvetica-Bold", textColor=header_colour, spaceAfter=6),
        "h2": _style("h2", fontSize=14, fontName="Helvetica-Bold", textColor=header_colour, spaceBefore=8, spaceAfter=4),
        "h3": _style("h3", fontSize=10, fontName="Helvetica-Bold", textColor=header_colour, spaceBefore=6, spaceAfter=3),
        "body": _style("body", fontSize=9),
        "right": _style("right", fontSize=9, alignment=2),
        "bold_right": _style("bold_right", fontSize=9, fontName="Helvetica-Bold", alignment=2),
    }


def _table_style(header_colour: colors.HexColor, stripe_colour: colors.HexColor) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), header_colour),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, stripe_colour]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


def _cover_page(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    settings: dict[str, str | None],
    fy: str,
    start: date,
    end: date,
    header_colour: colors.HexColor,
) -> None:
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph(settings.get("business_name") or "Your Business", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=2, color=header_colour))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph("ACCOUNTANT REPORT PACK", _make_styles(header_colour)["h2"])
    )
    story.append(Spacer(1, 6 * mm))

    meta = [
        ("Financial Year", fy),
        ("Period", f"{start:%d/%m/%Y}  to  {end:%d/%m/%Y}"),
        ("ABN", settings.get("business_abn") or "(not set)"),
        ("Generated", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    for label, value in meta:
        if not value:
            continue
        row = [[Paragraph(f"<b>{label}:</b>", styles["body"]), Paragraph(str(value), styles["body"])]]
        tbl = Table(row, colWidths=[45 * mm, 110 * mm])
        tbl.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(tbl)

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("<b>Contents</b>", styles["h3"]))
    for item in [
        "1. Profit & Loss Summary",
        "2. Invoice List",
        "3. Ledger - Income",
        "4. Ledger - Expenses",
        "5. ATO / BAS Summary",
    ]:
        story.append(Paragraph(item, styles["body"]))
    story.append(PageBreak())


def _section_header(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    number: int,
    title: str,
    header_colour: colors.HexColor,
) -> None:
    story.append(HRFlowable(width="100%", thickness=1.5, color=header_colour))
    story.append(Paragraph(f"{number}. {title}", styles["h2"]))
    story.append(Spacer(1, 2 * mm))


def _pl_section(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    invoices: list[Invoice],
    ledger: list[LedgerEntry],
    symbol: str,
    header_colour: colors.HexColor,
    stripe_colour: colors.HexColor,
) -> None:
    _section_header(story, styles, 1, "Profit & Loss Summary", header_colour)

    active_invoices = [inv for inv in invoices if inv.status not in ("cancelled", "void")]
    total_invoiced = sum(inv.total_cents for inv in active_invoices)
    total_paid = sum(
        sum(p.amount_cents for p in inv.payments if not p.is_reversed)
        for inv in active_invoices
    )
    outstanding = total_invoiced - total_paid

    ledger_income = sum(entry.amount_cents for entry in ledger if entry.entry_type == "in")
    ledger_expenses = sum(entry.amount_cents for entry in ledger if entry.entry_type == "out")
    net_profit = ledger_income - ledger_expenses

    rows = [
        [Paragraph("<b>Item</b>", styles["body"]), Paragraph("<b>Amount</b>", styles["bold_right"])],
        [Paragraph("Total Invoiced", styles["body"]), Paragraph(_fmt_cents(total_invoiced, symbol), styles["right"])],
        [Paragraph("Total Paid", styles["body"]), Paragraph(_fmt_cents(total_paid, symbol), styles["right"])],
        [Paragraph("Outstanding", styles["body"]), Paragraph(_fmt_cents(outstanding, symbol), styles["right"])],
        [Paragraph("", styles["body"]), Paragraph("", styles["right"])],
        [Paragraph("Ledger Income", styles["body"]), Paragraph(_fmt_cents(ledger_income, symbol), styles["right"])],
        [Paragraph("Ledger Expenses", styles["body"]), Paragraph(_fmt_cents(ledger_expenses, symbol), styles["right"])],
        [Paragraph("<b>Net Profit</b>", styles["body"]), Paragraph(_fmt_cents(net_profit, symbol), styles["bold_right"])],
    ]
    tbl = Table(rows, colWidths=[110 * mm, 40 * mm], hAlign="LEFT")
    tbl.setStyle(_table_style(header_colour, stripe_colour))
    story.append(tbl)
    story.append(PageBreak())


def _invoice_section(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    invoices: list[Invoice],
    symbol: str,
    header_colour: colors.HexColor,
    stripe_colour: colors.HexColor,
) -> None:
    _section_header(story, styles, 2, "Invoice List", header_colour)

    rows = [
        [
            Paragraph(h, styles["body"])
            for h in ["Date", "Invoice #", "Client", "Total", "Paid", "Balance", "Status"]
        ]
    ]
    total = paid_total = balance_total = 0
    for inv in sorted(invoices, key=lambda i: cast(date, i.issue_date)):
        paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
        balance = inv.total_cents - paid
        if inv.status not in ("cancelled", "void"):
            total += inv.total_cents
            paid_total += paid
            balance_total += balance
        rows.append(
            [
                Paragraph(str(inv.issue_date), styles["body"]),
                Paragraph(inv.number, styles["body"]),
                Paragraph(inv.client_name, styles["body"]),
                Paragraph(_fmt_cents(inv.total_cents, symbol), styles["right"]),
                Paragraph(_fmt_cents(paid, symbol), styles["right"]),
                Paragraph(_fmt_cents(balance, symbol), styles["right"]),
                Paragraph(inv.status, styles["body"]),
            ]
        )
    rows.append(
        [
            Paragraph("", styles["body"]),
            Paragraph("", styles["body"]),
            Paragraph("<b>TOTALS</b>", styles["body"]),
            Paragraph(_fmt_cents(total, symbol), styles["bold_right"]),
            Paragraph(_fmt_cents(paid_total, symbol), styles["bold_right"]),
            Paragraph(_fmt_cents(balance_total, symbol), styles["bold_right"]),
            Paragraph("", styles["body"]),
        ]
    )
    tbl = Table(rows, colWidths=[22 * mm, 24 * mm, 46 * mm, 22 * mm, 22 * mm, 22 * mm, 18 * mm], repeatRows=1)
    tbl.setStyle(_table_style(header_colour, stripe_colour))
    story.append(tbl)
    story.append(PageBreak())


def _ledger_section(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    ledger: list[LedgerEntry],
    symbol: str,
    header_colour: colors.HexColor,
    stripe_colour: colors.HexColor,
    section_num: int,
    title: str,
    entry_type: str,
) -> None:
    _section_header(story, styles, section_num, title, header_colour)

    entries = [e for e in ledger if e.entry_type == entry_type]
    by_cat: dict[str, list[LedgerEntry]] = {}
    for entry in entries:
        by_cat.setdefault(entry.category, []).append(entry)

    rows = [
        [Paragraph(h, styles["body"]) for h in ["Date", "Category", "Description", "Amount", "Reference"]]
    ]
    grand_total = 0
    for category in sorted(by_cat):
        cat_entries = by_cat[category]
        cat_total = sum(e.amount_cents for e in cat_entries)
        grand_total += cat_total
        for entry in cat_entries:
            rows.append(
                [
                    Paragraph(str(entry.date), styles["body"]),
                    Paragraph(category, styles["body"]),
                    Paragraph(entry.description, styles["body"]),
                    Paragraph(_fmt_cents(entry.amount_cents, symbol), styles["right"]),
                    Paragraph(entry.reference or "", styles["body"]),
                ]
            )
        rows.append(
            [
                Paragraph("", styles["body"]),
                Paragraph("", styles["body"]),
                Paragraph(f"<i>Subtotal - {category}</i>", styles["body"]),
                Paragraph(_fmt_cents(cat_total, symbol), styles["bold_right"]),
                Paragraph("", styles["body"]),
            ]
        )
    rows.append(
        [
            Paragraph("", styles["body"]),
            Paragraph("", styles["body"]),
            Paragraph("<b>TOTAL</b>", styles["body"]),
            Paragraph(_fmt_cents(grand_total, symbol), styles["bold_right"]),
            Paragraph("", styles["body"]),
        ]
    )
    tbl = Table(rows, colWidths=[22 * mm, 38 * mm, 64 * mm, 24 * mm, 24 * mm], repeatRows=1)
    tbl.setStyle(_table_style(header_colour, stripe_colour))
    story.append(tbl)
    story.append(PageBreak())


def _ato_section(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    invoices: list[Invoice],
    ledger: list[LedgerEntry],
    symbol: str,
    header_colour: colors.HexColor,
    stripe_colour: colors.HexColor,
    gst_rate: Decimal,
) -> None:
    _section_header(story, styles, 5, "ATO / BAS Summary", header_colour)

    active_invoices = [inv for inv in invoices if inv.status not in ("cancelled", "void")]
    sales_excl = sum(inv.subtotal_cents for inv in active_invoices)
    gst_collected = sum(inv.gst_cents for inv in active_invoices)
    sales_incl = sales_excl + gst_collected

    expenses_incl = sum(e.amount_cents for e in ledger if e.entry_type == "out")
    if gst_rate > 0:
        gst_paid = (
            (Decimal(expenses_incl) / Decimal(100)) * gst_rate / (Decimal(1) + gst_rate)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gst_paid_cents = int(gst_paid * Decimal(100))
    else:
        gst_paid_cents = 0
    expenses_excl = expenses_incl - gst_paid_cents
    net_gst = gst_collected - gst_paid_cents

    rows = [
        [Paragraph("<b>Item</b>", styles["body"]), Paragraph("<b>Amount</b>", styles["bold_right"])],
        [Paragraph("Sales (excl. GST)", styles["body"]), Paragraph(_fmt_cents(sales_excl, symbol), styles["right"])],
        [Paragraph("GST Collected (G1)", styles["body"]), Paragraph(_fmt_cents(gst_collected, symbol), styles["right"])],
        [Paragraph("Sales (incl. GST)", styles["body"]), Paragraph(_fmt_cents(sales_incl, symbol), styles["right"])],
        [Paragraph("", styles["body"]), Paragraph("", styles["right"])],
        [Paragraph("Expenses (incl. GST)", styles["body"]), Paragraph(_fmt_cents(expenses_incl, symbol), styles["right"])],
        [Paragraph("GST Credits (1B)", styles["body"]), Paragraph(_fmt_cents(gst_paid_cents, symbol), styles["right"])],
        [Paragraph("Expenses (excl. GST)", styles["body"]), Paragraph(_fmt_cents(expenses_excl, symbol), styles["right"])],
        [Paragraph("", styles["body"]), Paragraph("", styles["right"])],
        [Paragraph("<b>Net GST Payable</b>", styles["body"]), Paragraph(_fmt_cents(net_gst, symbol), styles["bold_right"])],
    ]
    tbl = Table(rows, colWidths=[110 * mm, 40 * mm], hAlign="LEFT")
    tbl.setStyle(_table_style(header_colour, stripe_colour))
    story.append(tbl)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("<b>Invoice GST Detail</b>", styles["h3"]))
    inv_rows = [
        [Paragraph(h, styles["body"]) for h in ["Date", "Invoice #", "Client", "Excl. GST", "GST", "Total", "Paid?"]]
    ]
    for inv in sorted(active_invoices, key=lambda i: cast(date, i.issue_date)):
        paid = sum(p.amount_cents for p in inv.payments if not p.is_reversed)
        inv_rows.append(
            [
                Paragraph(str(inv.issue_date), styles["body"]),
                Paragraph(inv.number, styles["body"]),
                Paragraph(inv.client_name, styles["body"]),
                Paragraph(_fmt_cents(inv.subtotal_cents, symbol), styles["right"]),
                Paragraph(_fmt_cents(inv.gst_cents, symbol), styles["right"]),
                Paragraph(_fmt_cents(inv.total_cents, symbol), styles["right"]),
                Paragraph("Yes" if paid >= inv.total_cents else "No", styles["body"]),
            ]
        )
    inv_tbl = Table(inv_rows, colWidths=[22 * mm, 22 * mm, 48 * mm, 22 * mm, 20 * mm, 22 * mm, 14 * mm], repeatRows=1)
    inv_tbl.setStyle(_table_style(header_colour, stripe_colour))
    story.append(inv_tbl)


def generate_accountant_pack_pdf(
    path: Path,
    fy: str,
    context: AppContext,
    settings: dict[str, str | None],
) -> None:
    """Build an accountant report pack PDF for the given financial year."""
    symbol = settings.get("currency_symbol") or "$"
    hdr_hex = settings.get("report_header_colour") or "#2C3E50"
    str_hex = settings.get("report_stripe_colour") or "#EBF5FB"
    header_colour = _hex_color(hdr_hex, "#2C3E50")
    stripe_colour = _hex_color(str_hex, "#EBF5FB")
    gst_rate = Decimal(settings.get("gst_rate") or "0.0")
    start_month = int(settings.get("financial_year_start_month") or 7)

    start, end = TaxYear(start_month).dates(fy)
    styles = _make_styles(header_colour)

    session = context.session
    invoices = list(
        session.execute(
            select(Invoice).where(Invoice.issue_date >= start, Invoice.issue_date <= end)
        )
        .scalars()
        .all()
    )
    ledger = list(
        session.execute(
            select(LedgerEntry).where(
                LedgerEntry.date >= start,
                LedgerEntry.date <= end,
                LedgerEntry.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Accountant Report Pack - {settings.get('business_name') or 'Business'} - {fy}",
        author=settings.get("business_name") or "Invoice & Receipt Manager",
    )

    story: list[Any] = []
    _cover_page(story, styles, settings, fy, start, end, header_colour)
    _pl_section(story, styles, invoices, ledger, symbol, header_colour, stripe_colour)
    _invoice_section(story, styles, invoices, symbol, header_colour, stripe_colour)
    _ledger_section(story, styles, ledger, symbol, header_colour, stripe_colour, 3, "Ledger - Income", "in")
    _ledger_section(story, styles, ledger, symbol, header_colour, stripe_colour, 4, "Ledger - Expenses", "out")
    _ato_section(story, styles, invoices, ledger, symbol, header_colour, stripe_colour, gst_rate)

    doc.build(story)
