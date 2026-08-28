"""Client statement of account PDF generator."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from invoice_manager.persistence.models import Invoice


def _fmt_cents(cents: int, symbol: str = "$") -> str:
    return f"{symbol}{cents / 100:,.2f}"


def _hex(colour: str | None, default: str) -> colors.Color:
    try:
        return colors.HexColor(colour or default)
    except Exception:
        return colors.HexColor(default)


def generate_client_statement_pdf(
    client: Any,
    invoices: list[Invoice],
    settings: dict[str, Any],
    output_path: Path,
    as_at: str | None = None,
) -> None:
    """Build a client statement of account PDF at ``output_path``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sym = settings.get("currency_symbol") or "$"
    biz = settings.get("business_name") or ""
    header_colour = _hex(settings.get("report_header_colour"), "#2C3E50")
    accent_colour = _hex(settings.get("report_accent_colour"), "#2980B9")
    stripe_colour = _hex(settings.get("report_stripe_colour"), "#EBF5FB")
    as_at = as_at or date.today().strftime("%d/%m/%Y")

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8)
    bold9 = ParagraphStyle("bold9", parent=normal, fontSize=9, fontName="Helvetica-Bold")
    h1 = ParagraphStyle(
        "h1", parent=normal, fontSize=16, fontName="Helvetica-Bold", textColor=header_colour
    )
    heading = ParagraphStyle(
        "heading",
        parent=normal,
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=accent_colour,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    story = []

    if biz:
        story.append(Paragraph(biz, h1))
        story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("STATEMENT OF ACCOUNT", heading))
    story.append(Spacer(1, 3 * mm))

    meta = Table(
        [
            [
                Paragraph("<b>To:</b>", small),
                Paragraph(client.name, bold9),
                Paragraph("<b>As at:</b>", small),
                Paragraph(as_at, small),
            ]
        ],
        colWidths=[15 * mm, 85 * mm, 20 * mm, 40 * mm],
    )
    meta.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])
    )
    story.append(meta)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=header_colour))
    story.append(Spacer(1, 4 * mm))

    headers = ["Date", "Invoice #", "Description", "Total", "Paid", "Balance"]
    widths = [22 * mm, 22 * mm, 65 * mm, 22 * mm, 22 * mm, 22 * mm]

    def _cell(text: str, align: int = TA_LEFT, bold: bool = False) -> Paragraph:
        return Paragraph(
            str(text),
            ParagraphStyle(
                "td",
                parent=normal,
                fontSize=8,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                alignment=align,
            ),
        )

    def _right(value: Any, bold: bool = False) -> Paragraph:
        return _cell(str(value), TA_RIGHT, bold=bold)

    def _header(text: str) -> Paragraph:
        return Paragraph(
            f"<b>{text}</b>",
            ParagraphStyle(
                "th",
                parent=normal,
                fontSize=8,
                fontName="Helvetica-Bold",
                textColor=colors.white,
                alignment=TA_CENTER,
            ),
        )

    rows = [[_header(h) for h in headers]]
    row_styles = []

    running_balance = 0
    total_invoiced = 0
    total_paid = 0

    for idx, inv in enumerate(invoices):
        payments = [p for p in inv.payments if not p.is_reversed]
        paid = sum(p.amount_cents for p in payments)
        total = inv.total_cents if not (inv.is_cancelled or inv.is_void) else 0
        balance = total - paid

        running_balance += balance
        total_invoiced += total
        total_paid += paid

        note = (inv.notes or "")[:60]
        rows.append(
            [
                _cell(str(inv.issue_date)),
                _cell(inv.number),
                _cell(note),
                _right(_fmt_cents(total, sym)),
                _right(_fmt_cents(paid, sym)),
                _right(_fmt_cents(running_balance, sym), bold=(running_balance > 0)),
            ]
        )

        row_idx = len(rows) - 1
        if idx % 2 == 1:
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), stripe_colour))

        for pmt in payments:
            pmt_ref = pmt.reference or pmt.method or ""
            pmt_style = ParagraphStyle(
                "pmt", parent=normal, fontSize=7.5, textColor=colors.HexColor("#1a7a1a")
            )
            pmt_r = ParagraphStyle(
                "pmt_r",
                parent=normal,
                fontSize=7.5,
                alignment=TA_RIGHT,
                textColor=colors.HexColor("#1a7a1a"),
            )
            rows.append(
                [
                    _cell(""),
                    _cell(""),
                    Paragraph(f"  ↳ Payment  {pmt.date}  {pmt_ref}", pmt_style),
                    _cell(""),
                    Paragraph(_fmt_cents(pmt.amount_cents, sym), pmt_r),
                    _cell(""),
                ]
            )

    rows.append(
        [
            _cell(""),
            _cell(""),
            _header("TOTALS"),
            _right(_fmt_cents(total_invoiced, sym), bold=True),
            _right(_fmt_cents(total_paid, sym), bold=True),
            _right(_fmt_cents(running_balance, sym), bold=True),
        ]
    )

    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_colour),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, -1), (-1, -1), header_colour),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, 0), 0.5, colors.white),
                ("LINEBELOW", (0, -1), (-1, -1), 1, header_colour),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
            + row_styles
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    outstanding = running_balance
    out_colour = colors.HexColor("#c0392b") if outstanding > 0 else colors.HexColor("#1a7a1a")
    summary_data = [
        [Paragraph("<b>Total Invoiced</b>", small), _right(_fmt_cents(total_invoiced, sym), True)],
        [Paragraph("<b>Total Paid</b>", small), _right(_fmt_cents(total_paid, sym), True)],
        [
            Paragraph(
                "<b>Amount Outstanding</b>",
                ParagraphStyle("out", parent=normal, fontSize=9, textColor=out_colour),
            ),
            _right(_fmt_cents(outstanding, sym), True),
        ],
    ]
    summary = Table(summary_data, colWidths=[50 * mm, 30 * mm], hAlign="RIGHT")
    summary.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 1, header_colour),
                ("LINEBELOW", (0, -1), (-1, -1), 1.5, header_colour),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary)

    doc.build(story)
