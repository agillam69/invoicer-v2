import time

import pytest
from sqlalchemy.exc import IntegrityError

from invoice_manager.application.auth import AuthenticationError, UserService
from invoice_manager.persistence.repositories import UserRepository

PASSWORD = "correct-horse-battery"


def test_first_admin_argon2id_and_login(session) -> None:
    service = UserService(delay_seconds=0)
    user = service.create_first_admin(session, "alex", "Alexander Gillam", "secret")
    session.commit()
    assert user.password_hash.startswith("$argon2id$")
    assert service.authenticate(session, "alex", "secret").id == user.id
    session.commit()
    session.expire_all()
    assert session.get(type(user), user.id).last_login_at is not None
    with pytest.raises(AuthenticationError):
        service.authenticate(session, "alex", "wrong")


def test_failed_login_delay_and_disabled_user(session) -> None:
    service = UserService(delay_seconds=0.02)
    user = service.create_first_admin(session, "alex", "Alex", "secret")
    session.commit()
    started = time.monotonic()
    with pytest.raises(AuthenticationError):
        service.authenticate(session, "alex", "wrong")
    assert time.monotonic() - started >= 0.02
    service.disable(user)
    session.commit()
    with pytest.raises(AuthenticationError):
        service.authenticate(session, "alex", "secret")


def test_password_is_never_stored_in_clear(session) -> None:
    service = UserService(delay_seconds=0)
    service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    stored = UserRepository(session).by_username("alex")
    assert stored is not None
    assert PASSWORD not in stored.password_hash


def test_no_universal_default_password_exists(session) -> None:
    service = UserService(delay_seconds=0)
    service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    for candidate in ("password", "admin", "Password1", "invoice", ""):
        with pytest.raises(AuthenticationError):
            service.authenticate(session, "alex", candidate)


def test_second_first_admin_is_refused(session) -> None:
    service = UserService(delay_seconds=0)
    service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    with pytest.raises(ValueError):
        service.create_first_admin(session, "someone-else", "Someone", PASSWORD)


def test_blank_passwords_are_refused(session) -> None:
    service = UserService(delay_seconds=0)
    with pytest.raises(ValueError):
        service.create_first_admin(session, "alex", "Alex", "")


def test_unknown_user_is_rejected_without_disclosure(session) -> None:
    service = UserService(delay_seconds=0)
    service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    with pytest.raises(AuthenticationError) as unknown:
        service.authenticate(session, "nobody", PASSWORD)
    with pytest.raises(AuthenticationError) as wrong_password:
        service.authenticate(session, "alex", "another-wrong-value")
    assert str(unknown.value) == str(wrong_password.value)


def test_duplicate_username_is_rejected(session) -> None:
    service = UserService(delay_seconds=0)
    admin = service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    with pytest.raises(IntegrityError):
        service.add_user(session, admin.username, "Impostor", PASSWORD)


def test_reset_password_replaces_the_previous_one(session) -> None:
    service = UserService(delay_seconds=0)
    admin = service.create_first_admin(session, "alex", "Alex", PASSWORD)
    bookkeeper = service.add_user(session, "bookkeeper", "Book Keeper", PASSWORD)
    session.commit()
    service.rename(bookkeeper, "Bookkeeper")
    service.reset_password(bookkeeper, "a-brand-new-password")
    session.commit()
    assert service.authenticate(session, "bookkeeper", "a-brand-new-password").id == bookkeeper.id
    with pytest.raises(AuthenticationError):
        service.authenticate(session, "bookkeeper", PASSWORD)
    assert bookkeeper.display_name == "Bookkeeper"
    assert admin.password_hash != bookkeeper.password_hash


def test_sql_injection_in_username_is_not_executed(session) -> None:
    service = UserService(delay_seconds=0)
    service.create_first_admin(session, "alex", "Alex", PASSWORD)
    session.commit()
    with pytest.raises(AuthenticationError):
        service.authenticate(session, "alex'; DROP TABLE users; --", PASSWORD)
    assert UserRepository(session).by_username("alex") is not None
