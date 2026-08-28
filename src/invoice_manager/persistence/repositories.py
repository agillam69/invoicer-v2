from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoice_manager.persistence.models import AuditEvent, Client, Invoice, User

Model = TypeVar("Model")


class Repository[Model]:
    def __init__(self, session: Session, model: type[Model]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: int) -> Model | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: Model) -> Model:
        self.session.add(entity)
        return entity

    def delete(self, entity: Model) -> None:
        self.session.delete(entity)

    def all(self) -> list[Model]:
        return list(self.session.scalars(select(self.model)).all())


class UserRepository(Repository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))


class ClientRepository(Repository[Client]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Client)


class InvoiceRepository(Repository[Invoice]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Invoice)


class AuditRepository(Repository[AuditEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditEvent)
