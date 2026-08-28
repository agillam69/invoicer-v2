"""Audit trail.

Audit rows are written with the same session as the business change, so they
commit or roll back together.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from invoice_manager.persistence.models import AuditEvent


def new_correlation_id() -> str:
    return str(uuid4())


def _as_json(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, default=str, sort_keys=True)


def record_audit_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    summary: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Append an audit event to the caller's transaction."""
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        user_id=user_id,
        before_json=_as_json(before),
        after_json=_as_json(after),
        correlation_id=correlation_id,
    )
    session.add(event)
    session.flush()
    return event
