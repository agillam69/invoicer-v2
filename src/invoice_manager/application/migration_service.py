"""Import legacy v1 CSV files into the v2 database."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import cast

from invoice_manager.domain.money import to_cents
from invoice_manager.domain.numbering import parse_number
from invoice_manager.domain.statuses import derive_invoice_status
from invoice_manager.domain.validation import parse_date
from invoice_manager.infrastructure.file_store import FileStore
from invoice_manager.persistence.models import Client, Invoice, InvoiceItem
from invoice_manager.persistence.repositories import (
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    MigrationIssueRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
)


class MigrationService:
    """Non-destructive importer for v1 CSV data."""

    def __init__(
        self,
        source_dir: Path,
        setting_repo: SettingRepository,
        client_repo: ClientRepository,
        service_repo: ServiceItemRepository,
        invoice_repo: InvoiceRepository,
        payment_repo: PaymentRepository,
        ledger_repo: LedgerRepository,
        issue_repo: MigrationIssueRepository,
        file_store: FileStore,
        payment_terms_days: int = 7,
    ) -> None:
        self.source_dir = Path(source_dir)
        self.settings = setting_repo
        self.clients = client_repo
        self.services = service_repo
        self.invoices = invoice_repo
        self.payments = payment_repo
        self.ledger = ledger_repo
        self.issues = issue_repo
        self.file_store = file_store
        self.payment_terms_days = payment_terms_days
        self._client_cache: dict[str, Client] = {}
        self._invoice_count = 0
        self._client_count = 0
        self._service_count = 0
        self._payment_count = 0
        self._ledger_count = 0
        self._issue_count = 0

    def run(self) -> dict[str, int]:
        """Import all recognised v1 files and return counts."""
        self._import_settings()
        self._import_clients()
        self._import_service_items()
        self._import_invoices()
        self._import_ledger()
        self._update_numbering()
        return {
            "clients": self._client_count,
            "services": self._service_count,
            "invoices": self._invoice_count,
            "payments": self._payment_count,
            "ledger": self._ledger_count,
            "issues": self._issue_count,
        }

    def _import_settings(self) -> None:
        path = self.source_dir / "settings.json"
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            for key, value in data.items():
                self.settings.set(key, str(value))
        except Exception as exc:  # noqa: BLE001
            self._add_issue("settings_import_error", "warn", str(exc), raw=str(exc))

    def _import_clients(self) -> None:
        path = self.source_dir / "clients.csv"
        if not path.exists():
            return
        for row in self._read_csv(path):
            name = row.get("name", "").strip()
            if not name:
                continue
            existing = self.clients.get_by_name(name)
            if existing:
                self._client_cache[name.lower()] = existing
                continue
            client = self.clients.create(
                name=name,
                contact_name=row.get("contact_name", "").strip() or None,
                phone=row.get("phone", "").strip() or None,
                email=row.get("email", "").strip() or None,
                address=row.get("address", "").strip() or None,
            )
            self._client_cache[name.lower()] = client
            self._client_count += 1

    def _import_service_items(self) -> None:
        path = self.source_dir / "service_items.csv"
        if not path.exists():
            return
        for row in self._read_csv(path):
            description = row.get("description", "").strip()
            if not description:
                continue
            self.services.create(
                description=description,
                unit_price_cents=to_cents(row.get("unit_price", "0")),
                taxable=(row.get("taxable", "").strip().lower() == "yes"),
                unit="ea",
            )
            self._service_count += 1

    def _import_invoices(self) -> None:
        path = self.source_dir / "invoices.csv"
        if not path.exists():
            return
        for row in self._read_csv(path):
            raw_number = row.get("invoice_number", "").strip()
            parsed = parse_number(raw_number)
            if parsed is None:
                self._add_issue(
                    "invalid_invoice_number", "error", f"Bad number: {raw_number}", raw=str(row)
                )
                continue
            prefix, seq = parsed
            if seq == 0:
                # ERROR / invalid placeholders
                self._add_issue(
                    "placeholder_invoice", "warn", f"Skipped {raw_number}", raw=str(row)
                )
                continue
            number = f"{prefix or 'INV'}-{seq:04d}" if prefix else f"INV-{seq:04d}"

            issue_date = parse_date(row.get("invoice_date", ""))
            if issue_date is None:
                self._add_issue(
                    "missing_invoice_date", "error", f"Skipped {raw_number}: no date", raw=str(row)
                )
                continue

            due_date = parse_date(row.get("due_date", ""))
            if due_date is None:
                due_date = issue_date + timedelta(days=self.payment_terms_days)

            client_name = row.get("client_name", "").strip()
            client = self._client_cache.get(client_name.lower()) or self.clients.get_by_name(
                client_name
            )
            if client is None:
                # Do not create active clients from invalid legacy values without review.
                self._add_issue(
                    "unknown_client",
                    "error",
                    f"Skipped {raw_number}: unknown client '{client_name}'",
                    raw=str(row),
                )
                continue

            subtotal_cents = to_cents(row.get("subtotal", "0"))
            gst_cents = to_cents(row.get("gst", "0"))
            total_cents = to_cents(row.get("total", "0")) or (subtotal_cents + gst_cents)

            invoice = self.invoices.create(
                number=number,
                sequence_number=seq,
                issue_date=issue_date,
                due_date=due_date,
                client_id=client.id,
                client_name=client.name,
                client_address=row.get("client_address", "").strip() or None,
                reference="",
                notes=row.get("notes", "").strip() or None,
                subtotal_cents=subtotal_cents,
                gst_cents=gst_cents,
                total_cents=total_cents,
                is_draft=False,
                is_void=False,
                is_cancelled=False,
                status="imported",
            )
            # v1 did not store line items; synthesise one line.
            InvoiceItem(
                invoice_id=invoice.id,
                description=invoice.notes or "Imported invoice total",
                quantity=1,
                unit="ea",
                unit_price_cents=subtotal_cents,
                taxable=gst_cents > 0,
                subtotal_cents=subtotal_cents,
                gst_cents=gst_cents,
                total_cents=total_cents,
                sort_order=0,
            )

            self._import_invoice_pdf(invoice, raw_number)
            self._derive_payment(invoice, row)

            invoice.status = derive_invoice_status(
                invoice_total_cents=invoice.total_cents,
                balance_cents=invoice.total_cents
                - sum(p.amount_cents for p in invoice.payments if not p.is_reversed),
                due_date=cast(date, invoice.due_date),
                is_cancelled=invoice.is_cancelled,
                is_void=invoice.is_void,
            ).value

            self._invoice_count += 1

    def _import_invoice_pdf(self, invoice: Invoice, raw_number: str) -> None:
        source_pdf = self.source_dir / "invoices" / f"invoice_{raw_number}.pdf"
        if not source_pdf.exists():
            source_pdf = self.source_dir / f"invoice_{raw_number}.pdf"
        if not source_pdf.exists():
            return
        dest = self.file_store.import_invoice_pdf(source_pdf, invoice.number)
        if dest:
            invoice.pdf_path = str(dest)

    def _derive_payment(self, invoice: Invoice, row: dict[str, str]) -> None:
        paid_flag = row.get("paid", "").strip().lower()
        total_cents = invoice.total_cents
        if paid_flag not in ("yes", "y", "true", "1") or total_cents <= 0:
            return
        paid_date = parse_date(row.get("paid_date", ""))
        if paid_date is None:
            paid_date = cast(date, invoice.issue_date)
            self._add_issue(
                "missing_payment_date",
                "warn",
                f"{invoice.number}: payment date missing, using invoice date",
                source_id=invoice.number,
            )
        payment = self.payments.create(
            invoice_id=invoice.id,
            amount_cents=total_cents,
            date=paid_date,
            method="legacy",
            reference=row.get("payment_note", "").strip() or None,
            is_reversed=False,
        )
        # Receipt is generated later; reserve a receipt number in Phase 4.
        payment.receipt_number = None
        self._payment_count += 1

    def _import_ledger(self) -> None:
        path = self.source_dir / "ledger.csv"
        if not path.exists():
            return
        # These categories are either double-counted by invoice payments or
        # belong to the removed student/course feature.
        excluded_categories = {"Invoice Payment", "Certification Fee", "Cert Budget"}
        for row in self._read_csv(path):
            if row.get("deleted", "").strip() not in ("", "0", "False", "false"):
                continue
            entry_date = parse_date(row.get("date", ""))
            if entry_date is None:
                continue
            category = row.get("category", "").strip()
            if not category:
                continue
            if category in excluded_categories:
                self._add_issue(
                    "skipped_ledger_category",
                    "info",
                    f"Skipped ledger row with excluded category '{category}'",
                    raw=str(row),
                )
                continue
            description = row.get("description", "").strip()
            amount = to_cents(row.get("amount", "0"))
            entry_type = row.get("type", "").strip().lower()
            if entry_type not in ("in", "out"):
                entry_type = "out"
            self.ledger.create(
                date=entry_date,
                entry_type=entry_type,
                category=category,
                description=description or category,
                amount_cents=amount,
                reference=row.get("reference", "").strip() or None,
                notes=row.get("notes", "").strip() or None,
            )
            self._ledger_count += 1

    def _update_numbering(self) -> None:
        next_number = self.settings.get_int("next_invoice_number", 1)
        max_seq = 0
        # Query via session is cheaper than repo method; use repo's session.
        for inv in self.invoices._session.query(Invoice).all():
            max_seq = max(max_seq, inv.sequence_number)
        new_next = max(max_seq + 1, next_number)
        self.settings.set("next_invoice_number", str(new_next))

    def _add_issue(
        self,
        issue_type: str,
        severity: str,
        message: str,
        source_id: str | None = None,
        raw: str | None = None,
    ) -> None:
        self.issues.create(
            source_id=source_id,
            issue_type=issue_type,
            severity=severity,
            message=message,
            raw_data=raw,
        )
        self._issue_count += 1

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
