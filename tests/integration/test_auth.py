"""Authentication tests (FR-AUTH-001..006)."""

from __future__ import annotations

import time

import pytest
from argon2 import PasswordHasher
from sqlalchemy.orm import Session

from invoice_manager.application.auth_service import (
    AuthError,
    AuthService,
    InvalidCredentialsError,
    normalise_username,
)
from invoice_manager.domain.validation import ValidationError
from invoice_manager.persistence.repositories import AuditRepository, UserRepository

PASSWORD = "correct-horse-battery"
pytestmark = [pytest.mark.integration]


@pytest.fixture
def auth(session: Session, hasher: PasswordHasher) -> AuthService:
    return AuthService(session, hasher=hasher, failed_login_delay_seconds=0.0)


def test_new_database_requires_first_run_admin(auth: AuthService) -> None:
    assert auth.requires_first_run_setup() is True

    user = auth.create_first_admin("alex", PASSWORD, display_name="Alexander Gillam")

    assert user.username == "alex"
    assert user.display_name == "Alexander Gillam"
    assert auth.requires_first_run_setup() is False


def test_second_first_run_admin_is_refused(auth: AuthService) -> None:
    auth.create_first_admin("alex", PASSWORD)
    with pytest.raises(AuthError):
        auth.create_first_admin("someone-else", PASSWORD)


def test_password_is_argon2id_hashed_and_never_stored_in_clear(
    auth: AuthService, session: Session
) -> None:
    auth.create_first_admin("alex", PASSWORD)

    stored = UserRepository(session).get_by_username("alex")
    assert stored is not None
    assert PASSWORD not in stored.password_hash
    assert stored.password_hash.startswith("$argon2id$")


def test_no_universal_default_password_exists(auth: AuthService) -> None:
    auth.create_first_admin("alex", PASSWORD)
    for candidate in ("password", "admin", "Password1", "invoice", ""):
        with pytest.raises((InvalidCredentialsError, ValidationError)):
            auth.authenticate("alex", candidate)


def test_authenticate_records_login_and_timestamp(auth: AuthService, session: Session) -> None:
    created = auth.create_first_admin("alex", PASSWORD)

    signed_in = auth.authenticate("ALEX", PASSWORD)

    assert signed_in.id == created.id
    stored = UserRepository(session).get(created.id)
    assert stored is not None
    assert stored.last_login_at is not None
    actions = [
        event.action for event in AuditRepository(session).list_for_entity("user", created.id)
    ]
    assert "user.login" in actions


def test_failed_login_is_audited_and_delayed(session: Session, hasher: PasswordHasher) -> None:
    delay_seconds = 0.2
    auth = AuthService(session, hasher=hasher, failed_login_delay_seconds=delay_seconds)
    created = auth.create_first_admin("alex", PASSWORD)

    started = time.monotonic()
    with pytest.raises(InvalidCredentialsError):
        auth.authenticate("alex", "wrong-password-value")
    elapsed = time.monotonic() - started

    assert elapsed >= delay_seconds
    actions = [
        event.action for event in AuditRepository(session).list_for_entity("user", created.id)
    ]
    assert "user.login_failed" in actions


def test_unknown_user_is_rejected_without_disclosure(auth: AuthService) -> None:
    auth.create_first_admin("alex", PASSWORD)
    with pytest.raises(InvalidCredentialsError) as unknown:
        auth.authenticate("nobody", PASSWORD)
    with pytest.raises(InvalidCredentialsError) as wrong_password:
        auth.authenticate("alex", "another-wrong-value")
    assert str(unknown.value) == str(wrong_password.value)


def test_disabled_user_cannot_sign_in(auth: AuthService) -> None:
    admin = auth.create_first_admin("alex", PASSWORD)
    second = auth.create_user("bookkeeper", PASSWORD, acting_user_id=admin.id)

    auth.set_active(second.id, False, acting_user_id=admin.id)

    with pytest.raises(InvalidCredentialsError):
        auth.authenticate("bookkeeper", PASSWORD)


def test_last_active_user_cannot_be_disabled(auth: AuthService) -> None:
    admin = auth.create_first_admin("alex", PASSWORD)
    with pytest.raises(AuthError):
        auth.set_active(admin.id, False, acting_user_id=admin.id)


def test_add_rename_and_reset_password(auth: AuthService, session: Session) -> None:
    admin = auth.create_first_admin("alex", PASSWORD)
    second = auth.create_user("bookkeeper", PASSWORD, acting_user_id=admin.id)

    auth.rename(second.id, "Book Keeper", acting_user_id=admin.id)
    auth.set_password(second.id, "a-brand-new-password", acting_user_id=admin.id)

    assert auth.authenticate("bookkeeper", "a-brand-new-password").display_name == "Book Keeper"
    with pytest.raises(InvalidCredentialsError):
        auth.authenticate("bookkeeper", PASSWORD)
    actions = [
        event.action for event in AuditRepository(session).list_for_entity("user", second.id)
    ]
    assert {"user.created", "user.renamed", "user.password_reset"} <= set(actions)


def test_duplicate_username_is_rejected(auth: AuthService) -> None:
    auth.create_first_admin("alex", PASSWORD)
    with pytest.raises(ValidationError):
        auth.create_user("ALEX", PASSWORD)


@pytest.mark.parametrize("password", ["", "   ", "short"])
def test_weak_passwords_are_rejected(auth: AuthService, password: str) -> None:
    with pytest.raises(ValidationError):
        auth.create_first_admin("alex", password)


@pytest.mark.parametrize("username", ["", "  ", "bad user", "bad@user"])
def test_invalid_usernames_are_rejected(username: str) -> None:
    with pytest.raises(ValidationError):
        normalise_username(username)


def test_sql_injection_in_username_is_not_executed(auth: AuthService, session: Session) -> None:
    auth.create_first_admin("alex", PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        auth.authenticate("alex'; DROP TABLE users; --", PASSWORD)

    assert UserRepository(session).get_by_username("alex") is not None
