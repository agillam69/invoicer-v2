"""Generate an overdue payment reminder PDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from invoice_manager.domain.money import Money
from invoice_manager.persistence.models import Invoice


def _get(settings: dict[str, Any], key: str, default: str = "") -> str:
    value = settings.get(key, default)
    if not value:
        return default
    return str(value)


def generate_reminder_pdf(
    invoice: Invoice, settings: dict[str, Any], output_path: Path
) -> Path:
    """Create a polite overdue reminder for the invoice."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    due_date = cast(date, invoice.due_date) if invoice.due_date else None
    days_overdue = (today - due_date).days if due_date else 0

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph(_get(settings, "business_name", "Reminder"), styles["Title"]))
    story.append(Paragraph(_get(settings, "business_address"), styles["Normal"]))
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph("<b>Overdue Payment Reminder</b>", styles["Heading2"]))
    story.append(Spacer(1, 6 * mm))

    balance_cents = invoice.total_cents - sum(
        p.amount_cents for p in invoice.payments if not p.is_reversed
    ) - sum(c.amount_cents for c in invoice.credits)

    meta = [
        ["Invoice number:", invoice.number],
        ["Client:", invoice.client_name],
        ["Issue date:", str(invoice.issue_date)],
        ["Due date:", str(invoice.due_date or "")],
        ["Days overdue:", str(days_overdue)],
        ["Amount due:", Money(cents=balance_cents).__str__()],
    ]
    story.append(Table(meta, colWidths=[40 * mm, 110 * mm]))
    story.append(Spacer(1, 8 * mm))

    story.append(
        Paragraph(
            "This is a friendly reminder that the above invoice is now overdue. "
            "Please arrange payment as soon as possible.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    if _get(settings, "bank_name") or _get(settings, "bank_account"):
        story.append(Paragraph("<b>Payment details</b>", styles["Heading3"]))
        payment_line = (
            f"Bank: {_get(settings, 'bank_name')}  |  "
            f"BSB: {_get(settings, 'bank_bsb')}  |  "
            f"Account: {_get(settings, 'bank_account')}  |  "
            f"Name: {_get(settings, 'bank_account_name')}"
        )
        story.append(Paragraph(payment_line, styles["Normal"]))
        story.append(Spacer(1, 6 * mm))

    footer = _get(settings, "report_footer", "Thank you for your business.")
    if footer:
        story.append(Paragraph(footer, styles["Normal"]))

    doc.build(story)
    return output_path
