"""Generate a receipt PDF for a payment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from invoice_manager.domain.money import Money
from invoice_manager.persistence.models import Invoice, Payment, Receipt


class ReceiptPDFBuilder:
    """Build a receipt PDF from a Payment and its Invoice."""

    def __init__(
        self, payment: Payment | Receipt, invoice: Invoice | None, settings: dict[str, Any]
    ) -> None:
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
        abn = self._get("business_abn")
        if abn:
            story.append(Paragraph(f"ABN: {abn}", styles["Normal"]))
        phone = self._get("business_phone")
        email = self._get("business_email")
        contact_bits = [b for b in [phone, email] if b]
        if contact_bits:
            story.append(Paragraph("  |  ".join(contact_bits), styles["Normal"]))
        story.append(Paragraph(self._get("business_address"), styles["Normal"]))
        story.append(Spacer(1, 8 * mm))

        title = self._get("receipt_title", "RECEIPT")
        number = self.payment.receipt_number if isinstance(self.payment, Payment) else self.payment.number
        story.append(Paragraph(f"<b>{title}</b> — {number}", styles["Heading2"]))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("<b>RECEIPT OF PAYMENT</b>", styles["Heading3"]))
        story.append(Spacer(1, 3 * mm))

        amount_paid = self.payment.amount_cents
        if self.invoice is not None:
            paid_total = sum(
                payment.amount_cents
                for payment in self.invoice.payments
                if not payment.is_reversed
            )
            credits = sum(credit.amount_cents for credit in self.invoice.credits)
            outstanding = max(0, self.invoice.total_cents - paid_total - credits)
            data = [
                ["Received from:", self.invoice.client_name],
                [self._get("receipt_invoice_label", "Invoice #:") or "Invoice #:", self.invoice.number],
                ["Invoice date:", str(self.invoice.issue_date)],
                ["Invoice amount:", str(Money(cents=self.invoice.total_cents))],
                [self._get("receipt_amount_label", "Amount paid:") or "Amount paid:", str(Money(cents=amount_paid))],
                [self._get("receipt_method_label", "Payment method:") or "Payment method:", self.payment.method or ""],
                [self._get("receipt_reference_label", "Payment reference:") or "Payment reference:", self.payment.reference or ""],
                ["Amount outstanding:", str(Money(cents=outstanding))],
            ]
        else:
            assert isinstance(self.payment, Receipt)
            data = [
                ["Received from:", self.payment.client_name],
                [self._get("receipt_date_label", "Date:") or "Date:", str(self.payment.date)],
                [self._get("receipt_amount_label", "Amount received:") or "Amount received:", str(Money(cents=amount_paid))],
                [self._get("receipt_method_label", "Payment method:") or "Payment method:", self.payment.method or ""],
                [self._get("receipt_reference_label", "Reference:") or "Reference:", self.payment.reference or ""],
                ["For:", self.payment.description or ""],
                ["Notes:", self.payment.notes or ""],
            ]
        story.append(Table(data, colWidths=[45 * mm, 110 * mm]))
        story.append(Spacer(1, 8 * mm))

        thank_you = self._get("receipt_thank_you", "Thank you for your payment.")
        if thank_you:
            story.append(Paragraph(thank_you, styles["Normal"]))

        doc.build(story)
        return output_path


def generate_receipt_pdf(
    payment: Payment | Receipt,
    invoice: Invoice | None,
    settings: dict[str, Any],
    output_path: Path,
) -> Path:
    return ReceiptPDFBuilder(payment, invoice, settings).build(output_path)
