from datetime import date

import pdfplumber

from invoice_manager.documents.client_statement_pdf import generate_client_statement_pdf
from invoice_manager.persistence.models import Client, Invoice, Payment


def test_client_statement_pdf_contains_client_and_totals(tmp_path):
    client = Client(name="Acme Corp")
    invoice = Invoice(
        number="INV-0001",
        sequence_number=1,
        issue_date=date(2026, 1, 15),
        due_date=date(2026, 2, 15),
        client=client,
        client_name=client.name,
        subtotal_cents=10000,
        gst_cents=1000,
        total_cents=11000,
        is_draft=False,
    )
    invoice.payments.append(
        Payment(
            invoice=invoice,
            amount_cents=5000,
            date=date(2026, 1, 20),
            method="EFT",
            receipt_number="RCT-0001",
        )
    )
    settings = {"business_name": "Test Business", "currency_symbol": "$"}
    output = tmp_path / "statement.pdf"
    generate_client_statement_pdf(client, [invoice], settings, output)

    assert output.exists()
    with pdfplumber.open(output) as pdf:
        text = " ".join(page.extract_text() or "" for page in pdf.pages)
    assert "Acme Corp" in text
    assert "INV-0001" in text
    assert "$110.00" in text
    assert "$50.00" in text
    assert "Amount Outstanding" in text
