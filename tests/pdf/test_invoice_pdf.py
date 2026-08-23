from datetime import date

import pdfplumber
from pypdf import PdfReader

from invoice_manager.application.client_service import ClientService
from invoice_manager.application.invoice_service import InvoiceItemData, InvoiceService
from invoice_manager.documents.invoice_pdf import InvoicePDF


def test_invoice_pdf_contains_snapshots_and_draft_watermark(session, tmp_path) -> None:
    client = ClientService().create(session, display_name="PDF Client")
    invoice = InvoiceService().create_draft(
        session,
        client,
        [InvoiceItemData(description="Design", quantity=1, unit_price_cents=12500)],
        invoice_date=date(2026, 6, 25),
        due_date=date(2026, 7, 2),
    )
    path = InvoicePDF().generate(invoice, tmp_path / "invoice.pdf")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert "INVOICE" in text
    assert "DRAFT" in text
    assert "PDF Client" in text
    assert "$125.00" in text
    with pdfplumber.open(path) as pdf:
        words = pdf.pages[0].extract_words()
        total_words = [word for word in words if word["text"] == "Total"]
        assert total_words
        assert all(0 <= word["x0"] < pdf.pages[0].width for word in total_words)


def test_invoice_pdf_repeats_headers_on_multiple_pages(session, tmp_path) -> None:
    client = ClientService().create(session, display_name="Many Lines")
    items = [
        InvoiceItemData(description=f"Long service line {index}", quantity=1, unit_price_cents=100)
        for index in range(70)
    ]
    invoice = InvoiceService().create_draft(session, client, items)
    path = InvoicePDF().generate(invoice, tmp_path / "many.pdf")
    reader = PdfReader(path)
    assert len(reader.pages) >= 2
    assert all("Description" in (page.extract_text() or "") for page in reader.pages)
