"""User authentication and password hashing."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from invoice_manager.persistence.repositories import UserRepository


class AuthService:
    """Authenticate users and manage the default admin account."""

    _ph = PasswordHasher()

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    def ensure_default_admin(self, password: str = "Admin") -> None:
        """Create the default admin user if no users exist."""
        if self._repo.list_users():
            return
        self.create_user("admin", password, role="admin")

    def create_user(self, username: str, password: str, role: str = "admin") -> None:
        if self._repo.get_by_username(username):
            raise ValueError(f"User '{username}' already exists")
        self._repo.create(
            username=username,
            password_hash=self._ph.hash(password),
            role=role,
        )

    def verify(self, username: str, password: str) -> bool:
        user = self._repo.get_by_username(username)
        if user is None:
            return False
        try:
            self._ph.verify(user.password_hash, password)
            return True
        except VerifyMismatchError:
            return False
