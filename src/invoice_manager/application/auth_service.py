"""Authentication and user administration (FR-AUTH-001..006)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NoReturn

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy.orm import Session

from invoice_manager.domain.validation import ValidationError, require_text
from invoice_manager.infrastructure.audit import record_audit_event
from invoice_manager.persistence.models import User
from invoice_manager.persistence.repositories import UserRepository

MINIMUM_PASSWORD_LENGTH = 10
FAILED_LOGIN_DELAY_SECONDS = 1.5


class AuthError(Exception):
    """Base class for authentication failures."""


class InvalidCredentialsError(AuthError):
    """Raised when the username or password is wrong, or the user is disabled."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    username: str
    display_name: str
    force_password_change: bool


def normalise_username(value: str) -> str:
    username = require_text(value, "Username").lower()
    if not username.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise ValidationError("Username may contain letters, numbers, dot, dash and underscore.")
    return username


def validate_password(value: str) -> str:
    password = require_text(value, "Password")
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MINIMUM_PASSWORD_LENGTH} characters.")
    return password


class AuthService:
    """Argon2id-backed login. There is no default or shared password."""

    def __init__(
        self,
        session: Session,
        *,
        hasher: PasswordHasher | None = None,
        failed_login_delay_seconds: float = FAILED_LOGIN_DELAY_SECONDS,
    ) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._hasher = hasher or PasswordHasher()
        self._failed_login_delay_seconds = failed_login_delay_seconds

    def requires_first_run_setup(self) -> bool:
        return self._users.count() == 0

    def create_user(
        self,
        username: str,
        password: str,
        *,
        display_name: str | None = None,
        force_password_change: bool = False,
        acting_user_id: int | None = None,
    ) -> AuthenticatedUser:
        cleaned_username = normalise_username(username)
        cleaned_password = validate_password(password)
        if self._users.get_by_username(cleaned_username) is not None:
            raise ValidationError(f"User {cleaned_username!r} already exists.")

        user = self._users.add(
            User(
                username=cleaned_username,
                display_name=(display_name or cleaned_username).strip(),
                password_hash=self._hasher.hash(cleaned_password),
                active=True,
                force_password_change=force_password_change,
            )
        )
        record_audit_event(
            self._session,
            action="user.created",
            entity_type="user",
            entity_id=user.id,
            summary=f"Created user {user.username}",
            user_id=acting_user_id,
            after={"username": user.username, "display_name": user.display_name},
        )
        return _to_authenticated(user)

    def create_first_admin(
        self, username: str, password: str, *, display_name: str | None = None
    ) -> AuthenticatedUser:
        if not self.requires_first_run_setup():
            raise AuthError("The first administrator already exists.")
        return self.create_user(username, password, display_name=display_name)

    def authenticate(self, username: str, password: str) -> AuthenticatedUser:
        user = self._users.get_by_username((username or "").strip().lower())
        if user is None or not user.active:
            self._reject()
        try:
            self._hasher.verify(user.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            record_audit_event(
                self._session,
                action="user.login_failed",
                entity_type="user",
                entity_id=user.id,
                summary=f"Failed login for {user.username}",
            )
            self._reject()

        if self._hasher.check_needs_rehash(user.password_hash):
            user.password_hash = self._hasher.hash(password)
        user.last_login_at = datetime.now(UTC)
        record_audit_event(
            self._session,
            action="user.login",
            entity_type="user",
            entity_id=user.id,
            summary=f"Signed in as {user.username}",
            user_id=user.id,
        )
        self._session.flush()
        return _to_authenticated(user)

    def set_password(
        self, user_id: int, new_password: str, *, acting_user_id: int | None = None
    ) -> None:
        user = self._require_user(user_id)
        user.password_hash = self._hasher.hash(validate_password(new_password))
        user.force_password_change = False
        record_audit_event(
            self._session,
            action="user.password_reset",
            entity_type="user",
            entity_id=user.id,
            summary=f"Reset password for {user.username}",
            user_id=acting_user_id,
        )
        self._session.flush()

    def set_active(self, user_id: int, active: bool, *, acting_user_id: int | None = None) -> None:
        user = self._require_user(user_id)
        if not active and self._only_active_user(user):
            raise AuthError("At least one active user must remain.")
        before = {"active": user.active}
        user.active = active
        record_audit_event(
            self._session,
            action="user.enabled" if active else "user.disabled",
            entity_type="user",
            entity_id=user.id,
            summary=f"{'Enabled' if active else 'Disabled'} user {user.username}",
            user_id=acting_user_id,
            before=before,
            after={"active": user.active},
        )
        self._session.flush()

    def rename(self, user_id: int, display_name: str, *, acting_user_id: int | None = None) -> None:
        user = self._require_user(user_id)
        before = {"display_name": user.display_name}
        user.display_name = require_text(display_name, "Display name")
        record_audit_event(
            self._session,
            action="user.renamed",
            entity_type="user",
            entity_id=user.id,
            summary=f"Renamed user {user.username}",
            user_id=acting_user_id,
            before=before,
            after={"display_name": user.display_name},
        )
        self._session.flush()

    def _require_user(self, user_id: int) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise AuthError(f"User {user_id} does not exist.")
        return user

    def _only_active_user(self, user: User) -> bool:
        return [candidate.id for candidate in self._users.list_all() if candidate.active] == [
            user.id
        ]

    def _reject(self) -> NoReturn:
        """Delay and fail without revealing which part of the input was wrong."""
        time.sleep(self._failed_login_delay_seconds)
        raise InvalidCredentialsError("Incorrect username or password.")


def _to_authenticated(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        force_password_change=user.force_password_change,
    )
