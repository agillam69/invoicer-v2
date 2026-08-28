"""Invoice lifecycle application service."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from invoice_manager.domain.invoices import InvoiceTotals, calculate_line_total
from invoice_manager.domain.money import Money
from invoice_manager.domain.numbering import NumberingService
from invoice_manager.domain.statuses import derive_invoice_status
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.models import Client, Invoice, InvoiceItem, Payment
from invoice_manager.persistence.repositories import (
    ClientRepository,
    InvoiceRepository,
    PaymentRepository,
    SettingRepository,
)


class InvoiceServiceError(Exception):
    pass


class InvoiceService:
    """Application service for creating, editing, issuing, and voiding invoices."""

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        client_repo: ClientRepository,
        payment_repo: PaymentRepository,
        setting_repo: SettingRepository,
        audit: AuditService,
        gst_rate: Decimal = Decimal("0.00"),
        payment_terms_days: int = 7,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._client_repo = client_repo
        self._payment_repo = payment_repo
        self._setting_repo = setting_repo
        self._audit = audit
        self._gst_rate = gst_rate
        self._payment_terms_days = payment_terms_days
        self._numbering = self._load_numbering()

    def _load_numbering(self) -> NumberingService:
        next_invoice = self._setting_repo.get_int("next_invoice_number", 1)
        next_receipt = self._setting_repo.get_int("next_receipt_number", 1)
        next_credit = self._setting_repo.get_int("next_credit_note_number", 1)
        return NumberingService(
            next_invoice=next_invoice,
            next_receipt=next_receipt,
            next_credit_note=next_credit,
        )

    def _persist_numbering(self) -> None:
        # NumberingService uses internal ints; map back by peeking next values.
        self._setting_repo.set("next_invoice_number", str(self._numbering.peek("invoice")[4:]))
        self._setting_repo.set("next_receipt_number", str(self._numbering.peek("receipt")[4:]))
        self._setting_repo.set(
            "next_credit_note_number", str(self._numbering.peek("credit_note")[3:])
        )

    def create_draft(
        self,
        client_id: int,
        invoice_date: date | None = None,
        due_date: date | None = None,
        notes: str | None = None,
    ) -> Invoice:
        client = (
            self._client_repo._session.query(Client).filter(Client.id == client_id).one_or_none()
        )
        if client is None:
            raise InvoiceServiceError("Client not found")
        today = date.today()
        issue_date = invoice_date or today
        due = due_date or (issue_date + timedelta(days=self._payment_terms_days))
        invoice = self._invoice_repo.create(
            number="DRAFT",
            sequence_number=-1,
            issue_date=issue_date,
            due_date=due,
            client_id=client.id,
            client_name=client.name,
            client_address=client.address,
            notes=notes,
            subtotal_cents=0,
            gst_cents=0,
            total_cents=0,
            is_draft=True,
            is_void=False,
            is_cancelled=False,
            status="draft",
        )
        self._audit.record("draft_created", "invoices", invoice.id, {"client": client.name})
        return invoice

    def add_line(
        self,
        invoice: Invoice,
        description: str,
        quantity: int,
        unit_price_cents: int,
        taxable: bool = True,
        discount_cents: int = 0,
    ) -> InvoiceItem:
        if not invoice.is_draft:
            raise InvoiceServiceError("Cannot edit an issued invoice")
        subtotal, gst, total = calculate_line_total(
            quantity,
            unit_price_cents,
            discount_cents,
            taxable,
            self._gst_rate,
        )
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=description.strip(),
            quantity=quantity,
            unit="ea",
            unit_price_cents=unit_price_cents,
            discount_cents=discount_cents,
            taxable=taxable,
            subtotal_cents=subtotal,
            gst_cents=gst,
            total_cents=total,
            sort_order=len(invoice.items),
        )
        invoice.items.append(item)
        self._recalc(invoice)
        self._audit.record("line_added", "invoice_items", item.id, {"invoice_id": invoice.id})
        return item

    def remove_line(self, invoice: Invoice, item: InvoiceItem) -> None:
        if not invoice.is_draft:
            raise InvoiceServiceError("Cannot edit an issued invoice")
        invoice.items.remove(item)
        self._recalc(invoice)
        self._audit.record("line_removed", "invoice_items", item.id, {"invoice_id": invoice.id})

    def issue(self, invoice: Invoice) -> Invoice:
        if not invoice.is_draft:
            raise InvoiceServiceError("Invoice is already issued")
        if not invoice.items:
            raise InvoiceServiceError("Cannot issue an invoice with no line items")
        number = self._numbering.reserve("invoice")
        invoice.number = number
        invoice.sequence_number = int(number.split("-")[1])
        invoice.is_draft = False
        invoice.status = "issued"
        self._persist_numbering()
        self._update_status(invoice)
        self._audit.record("invoice_issued", "invoices", invoice.id, {"number": number})
        return invoice

    def cancel(self, invoice: Invoice, reason: str) -> Invoice:
        if invoice.is_draft:
            raise InvoiceServiceError("Draft cannot be cancelled")
        if invoice.total_cents <= 0:
            raise InvoiceServiceError("Cannot cancel a zero-value invoice")
        invoice.is_cancelled = True
        self._update_status(invoice)
        self._audit.record("invoice_cancelled", "invoices", invoice.id, {"reason": reason})
        return invoice

    def void(self, invoice: Invoice, reason: str) -> Invoice:
        if invoice.is_draft:
            raise InvoiceServiceError("Draft cannot be voided")
        invoice.is_void = True
        self._update_status(invoice)
        self._audit.record("invoice_voided", "invoices", invoice.id, {"reason": reason})
        return invoice

    def recalc(self, invoice: Invoice) -> None:
        """Recalculate totals and status for an existing invoice."""
        self._recalc(invoice)
        self._update_status(invoice)

    def _recalc(self, invoice: Invoice) -> None:
        subtotal = 0
        gst = 0
        total = 0
        for item in invoice.items:
            s, g, t = calculate_line_total(
                item.quantity,
                item.unit_price_cents,
                item.discount_cents,
                item.taxable,
                self._gst_rate,
            )
            item.subtotal_cents = s
            item.gst_cents = g
            item.total_cents = t
            subtotal += s
            gst += g
            total += t
        invoice.subtotal_cents = subtotal
        invoice.gst_cents = gst
        invoice.total_cents = total

    def _update_status(self, invoice: Invoice) -> None:
        balance = self._balance(invoice)
        invoice.status = derive_invoice_status(
            invoice_total_cents=invoice.total_cents,
            balance_cents=balance.cents,
            due_date=cast(date, invoice.due_date),
            is_cancelled=invoice.is_cancelled,
            is_void=invoice.is_void,
        ).value

    def _balance(self, invoice: Invoice) -> Money:
        paid = sum(
            p.amount_cents
            for p in self._payment_repo._session.query(Payment)
            .filter(Payment.invoice_id == invoice.id, Payment.is_reversed.is_(False))
            .all()
        )
        return Money(cents=invoice.total_cents - paid)

    def get(self, invoice_id: int) -> Invoice | None:
        return (
            self._invoice_repo._session.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .one_or_none()
        )

    def list_invoices(self) -> Sequence[Invoice]:
        return list(
            self._invoice_repo._session.query(Invoice)
            .order_by(Invoice.issue_date.desc(), Invoice.sequence_number.desc())
            .all()
        )

    @staticmethod
    def totals_for_display(invoice: Invoice) -> InvoiceTotals:
        return InvoiceTotals(
            subtotal_cents=invoice.subtotal_cents,
            gst_cents=invoice.gst_cents,
            total_cents=invoice.total_cents,
        )
