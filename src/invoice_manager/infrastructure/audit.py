"""Structured audit-log service."""

from __future__ import annotations

import json
from typing import Any

from invoice_manager.persistence.repositories import AuditRepository


class AuditService:
    """Writes business-audit records via the repository."""

    def __init__(self, repository: AuditRepository, current_user: str = "system") -> None:
        self._repo = repository
        self._user = current_user

    def record(
        self,
        action: str,
        table_name: str | None = None,
        record_id: int | None = None,
        detail: dict[str, Any] | str | None = None,
    ) -> None:
        detail_str = ""
        if isinstance(detail, dict):
            detail_str = json.dumps(detail, default=str)
        elif detail is not None:
            detail_str = str(detail)
        self._repo.log(
            user=self._user,
            action=action,
            table_name=table_name,
            record_id=record_id,
            detail=detail_str,
        )

    def list_for_record(self, table_name: str, record_id: int) -> list[Any]:
        return self._repo.list_for_record(table_name, record_id)

    def set_user(self, username: str) -> None:
        self._user = username
