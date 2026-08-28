"""Audit trail tests (FR-LOG-001)."""

from __future__ import annotations

import json

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from invoice_manager.application.auth_service import AuthService
from invoice_manager.infrastructure.audit import new_correlation_id, record_audit_event
from invoice_manager.persistence.models import AuditEvent, Client
from invoice_manager.persistence.repositories import AuditRepository

pytestmark = [pytest.mark.integration]


def test_audit_event_stores_before_and_after_state(session: Session) -> None:
    client = Client(display_name="Town and Country Medical")
    session.add(client)
    session.flush()
    correlation_id = new_correlation_id()

    record_audit_event(
        session,
        action="client.updated",
        entity_type="client",
        entity_id=client.id,
        summary="Renamed client",
        before={"display_name": "Town & Country"},
        after={"display_name": client.display_name},
        correlation_id=correlation_id,
    )
    session.commit()

    stored = AuditRepository(session).list_for_entity("client", client.id)
    assert len(stored) == 1
    event = stored[0]
    assert event.correlation_id == correlation_id
    assert json.loads(event.before_json or "{}")["display_name"] == "Town & Country"
    assert json.loads(event.after_json or "{}")["display_name"] == "Town and Country Medical"
    assert event.timestamp_utc is not None


def test_audit_rolls_back_with_the_business_change(session: Session) -> None:
    """The audit row and the change it describes share one transaction."""
    client = Client(display_name="Specialist Event Medical")
    session.add(client)
    session.flush()
    record_audit_event(
        session,
        action="client.created",
        entity_type="client",
        entity_id=client.id,
        summary="Created client",
    )

    session.rollback()

    assert session.scalars(select(Client)).all() == []
    assert (
        session.scalars(select(AuditEvent).where(AuditEvent.action == "client.created")).all() == []
    )


def test_login_writes_audit_in_the_same_transaction(
    session: Session, hasher: PasswordHasher
) -> None:
    auth = AuthService(session, hasher=hasher, failed_login_delay_seconds=0.0)
    user = auth.create_first_admin("alex", "correct-horse-battery")
    session.commit()

    auth.authenticate("alex", "correct-horse-battery")
    session.commit()

    actions = [event.action for event in AuditRepository(session).list_for_entity("user", user.id)]
    assert actions == ["user.created", "user.login"]


def test_audit_events_are_ordered_and_listable(session: Session) -> None:
    for index in range(3):
        record_audit_event(
            session,
            action="system.check",
            entity_type="system",
            entity_id=index,
            summary=f"Check {index}",
        )
    session.commit()

    recent = AuditRepository(session).list_recent(limit=2)
    assert [event.summary for event in recent] == ["Check 2", "Check 1"]


def test_audit_table_is_append_only_from_the_application(session: Session) -> None:
    """Nothing in the application layer offers an update or delete path."""
    record_audit_event(
        session, action="system.check", entity_type="system", summary="Check", entity_id=1
    )
    session.commit()

    repository_methods = {name for name in dir(AuditRepository) if not name.startswith("_")}
    assert repository_methods == {"list_for_entity", "list_recent"}
    assert session.execute(text("select count(*) from audit_events")).scalar_one() == 1
