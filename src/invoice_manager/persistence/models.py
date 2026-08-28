"""SQLAlchemy models for every entity in build specification part F."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class BusinessProfile(Base, TimestampMixin):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    abn: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    payment_instructions: Mapped[str | None] = mapped_column(Text)
    bank_account_name: Mapped[str | None] = mapped_column(String(200))
    bank_bsb: Mapped[str | None] = mapped_column(String(10))
    bank_account_number: Mapped[str | None] = mapped_column(String(20))
    gst_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.0000"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), default="AUD", nullable=False)
    financial_year_start_month: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    default_terms_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    invoice_footer: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("gst_rate >= 0", name="ck_business_profiles_gst_rate"),
        CheckConstraint(
            "financial_year_start_month BETWEEN 1 AND 12",
            name="ck_business_profiles_fy_month",
        ),
        CheckConstraint("default_terms_days >= 0", name="ck_business_profiles_terms"),
    )


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    abn: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    billing_address: Mapped[str | None] = mapped_column(Text)
    default_terms_days: Mapped[int | None] = mapped_column(Integer)
    default_notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    invoices: Mapped[list[Invoice]] = relationship(back_populates="client")

    __table_args__ = (
        Index("ix_clients_display_name", "display_name"),
        CheckConstraint(
            "default_terms_days IS NULL OR default_terms_days >= 0",
            name="ck_clients_terms",
        ),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("type", "name", name="uq_categories_type_name"),
        CheckConstraint("type IN ('income', 'expense', 'service')", name="ck_categories_type"),
        Index("ix_categories_type", "type"),
    )


class ServiceItem(Base, TimestampMixin):
    __tablename__ = "service_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20), default="each", nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (CheckConstraint("unit_price_cents >= 0", name="ck_service_items_price"),)


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    original_number: Mapped[str | None] = mapped_column(String(40))
    status_override: Mapped[str | None] = mapped_column(String(20))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    client_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    client_abn_snapshot: Mapped[str | None] = mapped_column(String(20))
    client_contact_snapshot: Mapped[str | None] = mapped_column(String(120))
    client_email_snapshot: Mapped[str | None] = mapped_column(String(200))
    client_phone_snapshot: Mapped[str | None] = mapped_column(String(40))
    client_address_snapshot: Mapped[str | None] = mapped_column(Text)

    business_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    business_abn_snapshot: Mapped[str | None] = mapped_column(String(20))
    business_address_snapshot: Mapped[str | None] = mapped_column(Text)
    business_phone_snapshot: Mapped[str | None] = mapped_column(String(40))
    business_email_snapshot: Mapped[str | None] = mapped_column(String(200))
    payment_instructions_snapshot: Mapped[str | None] = mapped_column(Text)
    gst_registered_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gst_rate_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.0000"), nullable=False
    )

    reference: Mapped[str | None] = mapped_column(String(120))
    visible_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    footer_snapshot: Mapped[str | None] = mapped_column(Text)

    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    correction_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    client: Mapped[Client] = relationship(back_populates="invoices")
    items: Mapped[list[InvoiceItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.position"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    credit_notes: Mapped[list[CreditNote]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status_override IS NULL OR status_override IN ('Draft', 'Cancelled', 'Void')",
            name="ck_invoices_status_override",
        ),
        CheckConstraint("subtotal_cents >= 0", name="ck_invoices_subtotal"),
        CheckConstraint("gst_cents >= 0", name="ck_invoices_gst"),
        CheckConstraint("total_cents >= 0", name="ck_invoices_total"),
        CheckConstraint(
            "issued_at IS NULL OR canonical_number IS NOT NULL",
            name="ck_invoices_issued_has_number",
        ),
        Index("ix_invoices_client_id", "client_id"),
        Index("ix_invoices_invoice_date", "invoice_date"),
        Index("ix_invoices_due_date", "due_date"),
        Index("ix_invoices_reference", "reference"),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    service_item_id: Mapped[int | None] = mapped_column(ForeignKey("service_items.id"))
    service_code_snapshot: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_decimal: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="each", nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), default="none", nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal(0), nullable=False
    )
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    gst_rate_decimal: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal(0), nullable=False
    )
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("invoice_id", "position", name="uq_invoice_items_position"),
        CheckConstraint(
            "discount_type IN ('none', 'fixed', 'percent')", name="ck_invoice_items_discount_type"
        ),
        CheckConstraint("quantity_decimal >= 0", name="ck_invoice_items_quantity"),
        CheckConstraint("unit_price_cents >= 0", name="ck_invoice_items_price"),
        CheckConstraint("discount_cents >= 0", name="ck_invoice_items_discount"),
        CheckConstraint("gst_cents >= 0", name="ck_invoice_items_gst"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    payment_date: Mapped[date | None] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str | None] = mapped_column(String(40))
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reversal_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")
    receipt: Mapped[Receipt | None] = relationship(back_populates="payment")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payments_amount"),
        CheckConstraint(
            "reversed_at IS NULL OR reversal_reason IS NOT NULL",
            name="ck_payments_reversal_reason",
        ),
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    original_number: Mapped[str | None] = mapped_column(String(40))
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)

    payment: Mapped[Payment] = relationship(back_populates="receipt")


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    original_number: Mapped[str | None] = mapped_column(String(40))
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    credit_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    void_reason: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="credit_notes")
    items: Mapped[list[CreditNoteItem]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("total_cents >= 0", name="ck_credit_notes_total"),
        CheckConstraint(
            "voided_at IS NULL OR void_reason IS NOT NULL", name="ck_credit_notes_void_reason"
        ),
        Index("ix_credit_notes_invoice_id", "invoice_id"),
    )


class CreditNoteItem(Base):
    __tablename__ = "credit_note_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_decimal: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    gst_rate_decimal: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal(0), nullable=False
    )
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    credit_note: Mapped[CreditNote] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("credit_note_id", "position", name="uq_credit_note_items_position"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ex_gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supplier_payee: Mapped[str | None] = mapped_column(String(200))
    payment_method: Mapped[str | None] = mapped_column(String(40))
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reversal_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_ledger_entries_type"),
        CheckConstraint(
            "reversed_at IS NULL OR reversal_reason IS NOT NULL",
            name="ck_ledger_entries_reversal_reason",
        ),
        Index("ix_ledger_entries_entry_date", "entry_date"),
        Index("ix_ledger_entries_category_id", "category_id"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    managed_relative_path: Mapped[str | None] = mapped_column(Text)
    external_path: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(20), default="app", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    missing_last_checked: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint(
            "managed_relative_path IS NOT NULL OR external_path IS NOT NULL",
            name="ck_documents_has_location",
        ),
        Index("ix_documents_entity", "entity_type", "entity_id"),
        Index("ix_documents_sha256", "sha256"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(36))

    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_timestamp_utc", "timestamp_utc"),
    )


class NumberSequence(Base):
    __tablename__ = "number_sequences"

    sequence_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    next_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("next_value >= 1", name="ck_number_sequences_next_value"),
        CheckConstraint("padding >= 1", name="ck_number_sequences_padding"),
    )


class MigrationRun(Base):
    __tablename__ = "migration_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    source_manifest_hash: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str | None] = mapped_column(String(20))
    counts_json: Mapped[str | None] = mapped_column(Text)
    report_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    issues: Mapped[list[MigrationIssue]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class MigrationIssue(Base):
    __tablename__ = "migration_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("migration_runs.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    issue_code: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(30))
    source_key: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_resolution: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    run: Mapped[MigrationRun] = relationship(back_populates="issues")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'error')", name="ck_migration_issues_severity"
        ),
        Index("ix_migration_issues_run_id", "run_id"),
    )
