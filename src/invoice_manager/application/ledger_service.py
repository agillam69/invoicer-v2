"""Ledger application service."""

from __future__ import annotations

from datetime import date

from invoice_manager.infrastructure.audit import AuditService
from invoice_manager.persistence.models import LedgerEntry
from invoice_manager.persistence.repositories import LedgerRepository


class LedgerServiceError(Exception):
    pass


class LedgerService:
    """Application service for recording income and expenses."""

    def __init__(self, ledger_repo: LedgerRepository, audit: AuditService) -> None:
        self._ledger_repo = ledger_repo
        self._audit = audit

    def add_entry(
        self,
        entry_date: date,
        entry_type: str,
        category: str,
        description: str,
        amount_cents: int,
        reference: str | None = None,
        notes: str | None = None,
        attachment_path: str | None = None,
    ) -> LedgerEntry:
        if entry_type not in ("in", "out"):
            raise LedgerServiceError("entry_type must be 'in' or 'out'")
        if amount_cents <= 0:
            raise LedgerServiceError("amount must be positive")
        entry = self._ledger_repo.create(
            date=entry_date,
            entry_type=entry_type,
            category=category,
            description=description,
            amount_cents=amount_cents,
            reference=reference,
            notes=notes,
            attachment_path=attachment_path,
        )
        self._audit.record("ledger_entry_added", "ledger_entries", entry.id, {"category": category})
        return entry

    def update_entry(
        self,
        entry: LedgerEntry,
        entry_date: date,
        entry_type: str,
        category: str,
        description: str,
        amount_cents: int,
        reference: str | None = None,
        notes: str | None = None,
    ) -> None:
        if entry_type not in ("in", "out"):
            raise LedgerServiceError("entry_type must be 'in' or 'out'")
        if amount_cents <= 0:
            raise LedgerServiceError("amount must be positive")
        entry.date = entry_date  # type: ignore[assignment]
        entry.entry_type = entry_type
        entry.category = category
        entry.description = description
        entry.amount_cents = amount_cents
        entry.reference = reference
        entry.notes = notes
        self._audit.record(
            "ledger_entry_updated",
            "ledger_entries",
            entry.id,
            {"category": category, "description": description},
        )

    def delete_entry(self, entry: LedgerEntry, reason: str | None = None) -> None:
        entry.is_deleted = True
        detail = {"reason": reason} if reason else None
        self._audit.record("ledger_entry_deleted", "ledger_entries", entry.id, detail)

    def list_entries(self) -> list[LedgerEntry]:
        return self._ledger_repo.list_non_deleted()
