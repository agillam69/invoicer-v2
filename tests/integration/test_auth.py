import time

import pytest

from invoice_manager.application.auth import AuthenticationError, UserService


def test_first_admin_argon2id_and_login(session) -> None:
    service = UserService(delay_seconds=0)
    user = service.create_first_admin(session, "alex", "Alexander Gillam", "secret")
    session.commit()
    assert user.password_hash.startswith("$argon2id$")
    assert service.authenticate(session, "alex", "secret").id == user.id
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
