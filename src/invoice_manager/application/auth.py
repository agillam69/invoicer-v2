from __future__ import annotations

import logging
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from argon2.low_level import Type
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invoice_manager.persistence.clock import utc_now
from invoice_manager.persistence.models import User
from invoice_manager.persistence.repositories import UserRepository


class AuthenticationError(ValueError):
    """Raised when credentials are invalid."""


class UserService:
    def __init__(self, delay_seconds: float = 0.25) -> None:
        self.hasher = PasswordHasher(type=Type.ID)
        self.delay_seconds = delay_seconds
        self.logger = logging.getLogger("invoice_manager")

    def first_run_required(self, session: Session) -> bool:
        return session.scalar(select(func.count()).select_from(User)) == 0

    def create_first_admin(
        self, session: Session, username: str, display_name: str, password: str
    ) -> User:
        if not self.first_run_required(session):
            raise ValueError("first administrator already exists")
        if not password:
            raise ValueError("password is required")
        user = User(
            username=username.strip(),
            display_name=display_name.strip(),
            password_hash=self.hasher.hash(password),
            active=True,
        )
        session.add(user)
        session.flush()
        return user

    def add_user(self, session: Session, username: str, display_name: str, password: str) -> User:
        if not password:
            raise ValueError("password is required")
        user = User(
            username=username.strip(),
            display_name=display_name.strip(),
            password_hash=self.hasher.hash(password),
            active=True,
        )
        session.add(user)
        session.flush()
        return user

    def authenticate(self, session: Session, username: str, password: str) -> User:
        user = UserRepository(session).by_username(username.strip())
        try:
            if user is None or not user.active:
                raise AuthenticationError("invalid username or password")
            self.hasher.verify(user.password_hash, password)
        except (AuthenticationError, VerifyMismatchError, VerificationError) as exc:
            time.sleep(self.delay_seconds)
            self.logger.warning("Login failed")
            raise AuthenticationError("invalid username or password") from exc
        user.last_login_at = utc_now()
        self.logger.info("Login succeeded")
        return user

    def disable(self, user: User) -> None:
        user.active = False

    def rename(self, user: User, display_name: str) -> None:
        user.display_name = display_name.strip()

    def reset_password(self, user: User, new_password: str) -> None:
        if not new_password:
            raise ValueError("password is required")
        user.password_hash = self.hasher.hash(new_password)
        user.force_password_change = False
