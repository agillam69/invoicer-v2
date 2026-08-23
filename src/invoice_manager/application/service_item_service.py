from __future__ import annotations

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
        self,
        session: Session,
        *,
        name: str,
        code: str = "",
        description: str = "",
        unit: str = "each",
        unit_price_cents: int = 0,
        taxable: bool = False,
        category_id: int | None = None,
        active: bool = True,
    ) -> ServiceItem:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("service name is required")
        if not isinstance(unit_price_cents, int) or unit_price_cents < 0:
            raise ValueError("unit price cannot be negative")
        if (
            not isinstance(code, str)
            or not isinstance(description, str)
            or not isinstance(unit, str)
        ):
            raise ValueError("service text fields must be strings")
        if not unit.strip():
            raise ValueError("service unit is required")
        if not isinstance(category_id, int) and category_id is not None:
            raise ValueError("category ID must be an integer")
        if not isinstance(taxable, bool) or not isinstance(active, bool):
            raise ValueError("taxable and active must be boolean")
        item = ServiceItem(
            code=code.strip(),
            name=name.strip(),
            description=description.strip(),
            unit=unit.strip() or "each",
            unit_price_cents=unit_price_cents,
            taxable=taxable,
            category_id=category_id,
            active=active,
        )
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

    def update(
        self,
        session: Session,
        item: ServiceItem,
        *,
        name: str | None = None,
        code: str | None = None,
        description: str | None = None,
        unit: str | None = None,
        unit_price_cents: int | None = None,
        taxable: bool | None = None,
        category_id: int | None = None,
        active: bool | None = None,
    ) -> ServiceItem:
        before = {"name": item.name, "unit_price_cents": item.unit_price_cents}
        if name is not None and not isinstance(name, str):
            raise ValueError("service name is required")
        if code is not None and not isinstance(code, str):
            raise ValueError("service code must be a string")
        if description is not None and not isinstance(description, str):
            raise ValueError("service description must be a string")
        if unit is not None and not isinstance(unit, str):
            raise ValueError("service unit must be a string")
        if unit is not None and not unit.strip():
            raise ValueError("service unit is required")
        if name is not None:
            item.name = name.strip()
        if code is not None:
            item.code = code.strip()
        if description is not None:
            item.description = description.strip()
        if unit is not None:
            item.unit = unit.strip() or "each"
        if unit_price_cents is not None:
            if not isinstance(unit_price_cents, int):
                raise ValueError("unit price must be an integer")
            item.unit_price_cents = unit_price_cents
        if taxable is not None:
            if not isinstance(taxable, bool):
                raise ValueError("taxable must be boolean")
            item.taxable = taxable
        if category_id is not None:
            if not isinstance(category_id, int):
                raise ValueError("category ID must be an integer")
            item.category_id = category_id
        if active is not None:
            if not isinstance(active, bool):
                raise ValueError("active must be boolean")
            item.active = active
        if (
            not item.name.strip()
            or not isinstance(item.unit_price_cents, int)
            or item.unit_price_cents < 0
            or not isinstance(item.taxable, bool)
            or not isinstance(item.active, bool)
        ):
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
        if not isinstance(active, bool):
            raise ValueError("active must be boolean")
        item.active = active
        session.flush()
        self.audit.record(
            session,
            action="activate" if active else "deactivate",
            entity_type="service_item",
            entity_id=item.id,
            summary="Changed service item active state",
        )
