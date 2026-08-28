from datetime import date

import pdfplumber

from invoice_manager.documents.receipt_pdf import generate_receipt_pdf
from invoice_manager.persistence.models import Client, Invoice, Payment


def test_receipt_pdf_contains_invoice_and_amount(tmp_path):
    client = Client(name="Acme Corp")
    invoice = Invoice(
        number="INV-0002",
        sequence_number=2,
        issue_date=date(2026, 1, 15),
        due_date=date(2026, 2, 15),
        client=client,
        client_name=client.name,
        subtotal_cents=5000,
        gst_cents=0,
        total_cents=5000,
    )
    payment = Payment(
        invoice=invoice,
        amount_cents=5000,
        date=date(2026, 1, 20),
        method="EFT",
        receipt_number="RCT-0001",
    )
    settings = {"business_name": "Test Business", "thank_you_note": "Thanks!"}
    output = tmp_path / "receipt.pdf"
    generate_receipt_pdf(payment, invoice, settings, output)

    assert output.exists()
    with pdfplumber.open(output) as pdf:
        text = " ".join(page.extract_text() or "" for page in pdf.pages)
    assert "RCT-0001" in text
    assert "INV-0002" in text
    assert "$50.00" in text
    assert "EFT" in text
