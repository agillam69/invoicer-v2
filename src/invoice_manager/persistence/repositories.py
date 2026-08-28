"""Repository classes for persistence access."""

from __future__ import annotations

from sqlalchemy.orm import Session

from invoice_manager.persistence.models import AuditLog, Setting, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        return self._session.query(User).filter(User.username == username.strip()).one_or_none()

    def create(self, username: str, password_hash: str, role: str = "admin") -> User:
        user = User(
            username=username.strip(),
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def list_users(self) -> list[User]:
        return list(self._session.query(User).order_by(User.username).all())


class SettingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> str | None:
        row = self._session.query(Setting).filter(Setting.key == key).one_or_none()
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._session.query(Setting).filter(Setting.key == key).one_or_none()
        if row is None:
            row = Setting(key=key, value=value)
            self._session.add(row)
        else:
            row.value = value
        self._session.flush()

    def get_int(self, key: str, default: int = 0) -> int:
        raw = self.get(key)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            return default


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        user: str,
        action: str,
        table_name: str | None = None,
        record_id: int | None = None,
        detail: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user=user,
            action=action,
            table_name=table_name,
            record_id=record_id,
            detail=detail,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_recent(self, limit: int = 500) -> list[AuditLog]:
        return list(
            self._session.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
        )
