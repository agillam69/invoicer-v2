"""Generate a receipt PDF for a payment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from invoice_manager.domain.money import Money
from invoice_manager.persistence.models import Invoice, Payment


class ReceiptPDFBuilder:
    """Build a receipt PDF from a Payment and its Invoice."""

    def __init__(self, payment: Payment, invoice: Invoice, settings: dict[str, Any]) -> None:
        self.payment = payment
        self.invoice = invoice
        self.settings = settings

    def _get(self, key: str, default: str = "") -> str:
        value = self.settings.get(key, default)
        if value is None:
            return ""
        return str(value)

    def build(self, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
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

        story.append(Paragraph(self._get("business_name", "Receipt"), styles["Title"]))
        story.append(Paragraph(self._get("business_address"), styles["Normal"]))
        story.append(Spacer(1, 6 * mm))

        story.append(
            Paragraph(f"<b>RECEIPT</b> — {self.payment.receipt_number}", styles["Heading2"])
        )
        data = [
            ["Invoice:", self.invoice.number],
            ["Date:", str(self.payment.date)],
            ["Amount:", str(Money(cents=self.payment.amount_cents))],
            ["Method:", self.payment.method or ""],
            ["Reference:", self.payment.reference or ""],
        ]
        story.append(Table(data, colWidths=[35 * mm, 120 * mm]))
        story.append(Spacer(1, 8 * mm))

        thank_you = self._get("thank_you_note", "Thank you for your payment.")
        if thank_you:
            story.append(Paragraph(thank_you, styles["Normal"]))

        doc.build(story)
        return output_path


def generate_receipt_pdf(
    payment: Payment, invoice: Invoice, settings: dict[str, Any], output_path: Path
) -> Path:
    return ReceiptPDFBuilder(payment, invoice, settings).build(output_path)
