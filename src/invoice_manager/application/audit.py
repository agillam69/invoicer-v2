from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from invoice_manager.persistence.models import AuditEvent


class AuditService:
    def record(self, session: Session, *, action: str, entity_type: str,
               entity_id: int | None, summary: str, user_id: int | None = None,
               before: Any = None, after: Any = None) -> AuditEvent:
        event = AuditEvent(
            action=action, entity_type=entity_type, entity_id=entity_id,
            summary=summary, user_id=user_id,
            before_json=json.dumps(before, default=str) if before is not None else None,
            after_json=json.dumps(after, default=str) if after is not None else None,
            correlation_id=str(uuid.uuid4()),
        )
        session.add(event)
        return event
