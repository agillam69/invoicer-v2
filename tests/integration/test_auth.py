import pytest

from invoice_manager.application.auth_service import AuthService


def test_default_admin_created_on_first_run(user_repo):
    auth = AuthService(user_repo)
    auth.ensure_default_admin()
    user = user_repo.get_by_username("admin")
    assert user is not None
    assert user.role == "admin"


def test_default_admin_only_once(user_repo):
    auth = AuthService(user_repo)
    auth.ensure_default_admin()
    auth.ensure_default_admin()
    assert len(user_repo.list_users()) == 1


def test_verify_correct_password(user_repo):
    auth = AuthService(user_repo)
    auth.create_user("alice", "secret")
    assert auth.verify("alice", "secret") is True


def test_verify_wrong_password(user_repo):
    auth = AuthService(user_repo)
    auth.create_user("alice", "secret")
    assert auth.verify("alice", "wrong") is False


def test_verify_missing_user(user_repo):
    auth = AuthService(user_repo)
    assert auth.verify("nobody", "secret") is False


def test_cannot_create_duplicate_user(user_repo):
    auth = AuthService(user_repo)
    auth.create_user("alice", "secret")
    with pytest.raises(ValueError):
        auth.create_user("alice", "other")
