"""Tests for the accountant pack PDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pdfplumber

from invoice_manager.documents.accountant_pack_pdf import generate_accountant_pack_pdf
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    AuditRepository,
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
)


class _FakeContext:
    """Minimal context stand-in for the PDF builder."""

    def __init__(self, tmp_path: Path):
        self.config = AppConfig(tmp_path)
        self.database = Database(self.config.db_path())
        self.database.create_schema()
        self.session = self.database.new_session()
        self.client_repo = ClientRepository(self.session)
        self.invoice_repo = InvoiceRepository(self.session)
        self.payment_repo = PaymentRepository(self.session)
        self.service_repo = ServiceItemRepository(self.session)
        self.ledger_repo = LedgerRepository(self.session)
        self.setting_repo = SettingRepository(self.session)
        self.audit = AuditService(AuditRepository(self.session), "test")

    def close(self):
        self.session.close()
        self.database.engine.dispose()


def test_accountant_pack_contains_sections(tmp_path):
    ctx = _FakeContext(tmp_path)
    try:
        client = ctx.client_repo.create(name="Acme Corp")
        ctx.setting_repo.set("next_invoice_number", "1")
        ctx.setting_repo.set("next_receipt_number", "1")
        invoice = ctx.invoice_repo.create(
            number="INV-0001",
            sequence_number=1,
            issue_date=date(2025, 8, 15),
            due_date=date(2025, 8, 22),
            client_id=client.id,
            client_name=client.name,
            subtotal_cents=10000,
            gst_cents=1000,
            total_cents=11000,
            status="issued",
            is_draft=False,
        )
        ctx.payment_repo.create(
            invoice_id=invoice.id,
            amount_cents=11000,
            date=date(2025, 8, 16),
            method="Bank",
        )
        ctx.ledger_repo.create(
            date=date(2025, 8, 10),
            entry_type="out",
            category="Office",
            description="Stationery",
            amount_cents=2200,
        )

        settings = {
            "business_name": "Test Business",
            "business_abn": "12345678901",
            "currency_symbol": "$",
            "report_header_colour": "#2C3E50",
            "report_stripe_colour": "#EBF5FB",
            "gst_rate": "0.10",
        }
        output = tmp_path / "accountant_pack_2025-2026.pdf"
        generate_accountant_pack_pdf(output, "2025-2026", ctx, settings)  # type: ignore[arg-type]

        with pdfplumber.open(output) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "ACCOUNTANT REPORT PACK" in text
        assert "Profit & Loss Summary" in text
        assert "Invoice List" in text
        assert "Ledger - Income" in text
        assert "Ledger - Expenses" in text
        assert "ATO / BAS Summary" in text
        assert "Test Business" in text
        assert "INV-0001" in text
    finally:
        ctx.close()
