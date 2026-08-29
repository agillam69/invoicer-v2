from datetime import date

import pdfplumber

from invoice_manager.documents.receipt_docx import generate_receipt_docx
from invoice_manager.documents.receipt_pdf import generate_receipt_pdf
from invoice_manager.documents.receipt_xlsx import generate_receipt_xlsx
from invoice_manager.persistence.models import Client, Invoice, Payment, Receipt


def test_manual_receipt_exports_pdf_word_and_excel(tmp_path):
    receipt = Receipt(
        number="RCT-0042",
        client_name="Walk-in Client",
        date=date(2026, 8, 30),
        amount_cents=12500,
        method="Cash",
        reference="REF-42",
        description="Consulting",
    )
    settings = {"business_name": "Test Business"}
    pdf = generate_receipt_pdf(receipt, None, settings, tmp_path / "manual.pdf")
    docx = generate_receipt_docx(receipt, None, settings, tmp_path / "manual.docx")
    xlsx = generate_receipt_xlsx(receipt, None, settings, tmp_path / "manual.xlsx")
    assert pdf.exists()
    assert docx.exists()
    assert xlsx.exists()
    with pdfplumber.open(pdf) as document:
        text = " ".join(page.extract_text() or "" for page in document.pages)
    assert "RCT-0042" in text
    assert "Walk-in Client" in text
    assert "$125.00" in text


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
