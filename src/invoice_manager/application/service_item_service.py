from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoice_manager.application.audit import AuditService
from invoice_manager.persistence.models import ServiceItem


class ServiceItemService:
    def __init__(self, audit: AuditService | None = None) -> None:
        self.audit = audit or AuditService()

    def list(
        self, session: Session, search: str = "", *, active_only: bool = False
    ) -> list[ServiceItem]:
        stmt = select(ServiceItem).order_by(ServiceItem.name)
        if active_only:
            stmt = stmt.where(ServiceItem.active.is_(True))
        if search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                ServiceItem.name.ilike(term)
                | ServiceItem.code.ilike(term)
                | ServiceItem.description.ilike(term)
            )
        return list(session.scalars(stmt).all())

    def create(
        self, session: Session, *, name: str, unit_price_cents: int, **values: Any
    ) -> ServiceItem:
        if not name.strip():
            raise ValueError("service name is required")
        if unit_price_cents < 0:
            raise ValueError("unit price cannot be negative")
        item = ServiceItem(name=name.strip(), unit_price_cents=unit_price_cents, **values)
        session.add(item)
        session.flush()
        self.audit.record(
            session,
            action="create",
            entity_type="service_item",
            entity_id=item.id,
            summary="Created service item",
        )
        return item

    def update(self, session: Session, item: ServiceItem, **values: Any) -> ServiceItem:
        before = {"name": item.name, "unit_price_cents": item.unit_price_cents}
        for key, value in values.items():
            if key in {"id"} or not hasattr(item, key):
                raise ValueError(f"invalid service field: {key}")
            setattr(item, key, value)
        if not item.name.strip() or item.unit_price_cents < 0:
            raise ValueError("invalid service item")
        session.flush()
        self.audit.record(
            session,
            action="update",
            entity_type="service_item",
            entity_id=item.id,
            summary="Updated service item",
            before=before,
            after={"name": item.name, "unit_price_cents": item.unit_price_cents},
        )
        return item

    def set_active(self, session: Session, item: ServiceItem, active: bool) -> None:
        item.active = active
        self.audit.record(
            session,
            action="activate" if active else "deactivate",
            entity_type="service_item",
            entity_id=item.id,
            summary="Changed service item active state",
        )
