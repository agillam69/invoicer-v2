"""Payment and receipt application service."""

from __future__ import annotations

from datetime import date
from typing import cast

from invoice_manager.domain.numbering import NumberingService
from invoice_manager.domain.statuses import derive_invoice_status
from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.models import Invoice, Payment
from invoice_manager.persistence.repositories import (
    InvoiceRepository,
    PaymentRepository,
    SettingRepository,
)


class PaymentServiceError(Exception):
    pass


class PaymentService:
    """Record payments, reverse payments, and issue receipts."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        invoice_repo: InvoiceRepository,
        setting_repo: SettingRepository,
        audit: AuditService,
    ) -> None:
        self._payment_repo = payment_repo
        self._invoice_repo = invoice_repo
        self._setting_repo = setting_repo
        self._audit = audit
        self._numbering = self._load_numbering()

    def _load_numbering(self) -> NumberingService:
        next_receipt = self._setting_repo.get_int("next_receipt_number", 1)
        next_credit = self._setting_repo.get_int("next_credit_note_number", 1)
        next_invoice = self._setting_repo.get_int("next_invoice_number", 1)
        return NumberingService(
            next_invoice=next_invoice,
            next_receipt=next_receipt,
            next_credit_note=next_credit,
        )

    def _persist_numbering(self) -> None:
        self._setting_repo.set("next_receipt_number", str(int(self._numbering.peek("receipt")[4:])))
        self._setting_repo.set(
            "next_credit_note_number", str(int(self._numbering.peek("credit_note")[3:]))
        )

    def record(
        self,
        invoice: Invoice,
        amount_cents: int,
        payment_date: date,
        method: str,
        reference: str | None = None,
        notes: str | None = None,
        generate_receipt: bool = True,
    ) -> Payment:
        if invoice.is_draft:
            raise PaymentServiceError("Cannot record payment against a draft invoice")
        if invoice.is_void:
            raise PaymentServiceError("Cannot record payment against a void invoice")
        if amount_cents <= 0:
            raise PaymentServiceError("Payment amount must be positive")

        payment = self._payment_repo.create(
            invoice_id=invoice.id,
            amount_cents=amount_cents,
            date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
            is_reversed=False,
        )
        if generate_receipt:
            payment.receipt_number = self._numbering.reserve("receipt")
            self._persist_numbering()
        self._update_invoice_status(invoice)
        self._audit.record(
            "payment_recorded",
            "payments",
            payment.id,
            {"invoice": invoice.number, "amount_cents": amount_cents},
        )
        return payment

    def reverse(self, payment: Payment, reason: str) -> Payment:
        if payment.is_reversed:
            raise PaymentServiceError("Payment is already reversed")
        payment.is_reversed = True
        payment.reversal_reason = reason
        invoice = payment.invoice
        if invoice is not None:
            self._update_invoice_status(invoice)
        self._audit.record("payment_reversed", "payments", payment.id, {"reason": reason})
        return payment

    def _update_invoice_status(self, invoice: Invoice) -> None:
        total_paid = sum(p.amount_cents for p in invoice.payments if not p.is_reversed)
        balance = invoice.total_cents - total_paid
        invoice.status = derive_invoice_status(
            invoice_total_cents=invoice.total_cents,
            balance_cents=balance,
            due_date=cast(date, invoice.due_date),
            is_cancelled=invoice.is_cancelled,
            is_void=invoice.is_void,
        ).value

    def list_by_invoice(self, invoice: Invoice) -> list[Payment]:
        return list(
            self._payment_repo._session.query(Payment)
            .filter(Payment.invoice_id == invoice.id)
            .order_by(Payment.date)
            .all()
        )
