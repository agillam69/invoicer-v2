"""Repositories: the only place that talks to SQLAlchemy for reads/writes."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoice_manager.persistence.models import (
    AuditEvent,
    BusinessProfile,
    Client,
    Invoice,
    NumberSequence,
    User,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalars(
            select(User).where(User.username == username.strip().lower())
        ).first()

    def count(self) -> int:
        return len(self._session.scalars(select(User.id)).all())

    def list_all(self) -> Sequence[User]:
        return self._session.scalars(select(User).order_by(User.username)).all()


class ClientRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, client: Client) -> Client:
        self._session.add(client)
        self._session.flush()
        return client

    def get(self, client_id: int) -> Client | None:
        return self._session.get(Client, client_id)

    def list_active(self) -> Sequence[Client]:
        return self._session.scalars(
            select(Client).where(Client.active.is_(True)).order_by(Client.display_name)
        ).all()


class InvoiceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        self._session.flush()
        return invoice

    def get(self, invoice_id: int) -> Invoice | None:
        return self._session.get(Invoice, invoice_id)

    def get_by_number(self, canonical_number: str) -> Invoice | None:
        return self._session.scalars(
            select(Invoice).where(Invoice.canonical_number == canonical_number)
        ).first()

    def list_recent(self, limit: int = 20) -> Sequence[Invoice]:
        return self._session.scalars(
            select(Invoice).order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(limit)
        ).all()


class NumberSequenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, sequence_type: str) -> NumberSequence | None:
        return self._session.get(NumberSequence, sequence_type, with_for_update=True)

    def upsert(self, sequence: NumberSequence) -> NumberSequence:
        self._session.add(sequence)
        self._session.flush()
        return sequence


class BusinessProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current(self) -> BusinessProfile | None:
        return self._session.scalars(
            select(BusinessProfile)
            .where(BusinessProfile.is_current.is_(True))
            .order_by(BusinessProfile.id.desc())
        ).first()


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_entity(self, entity_type: str, entity_id: int) -> Sequence[AuditEvent]:
        return self._session.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.timestamp_utc, AuditEvent.id)
        ).all()

    def list_recent(self, limit: int = 100) -> Sequence[AuditEvent]:
        return self._session.scalars(
            select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        ).all()
