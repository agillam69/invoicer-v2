import pytest

from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    AuditRepository,
    SettingRepository,
    UserRepository,
)


@pytest.fixture
def tmp_db(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.drop_schema()
    db.create_schema()
    session = db.new_session()
    try:
        yield db, session
    finally:
        session.close()
        db.engine.dispose()


@pytest.fixture
def user_repo(tmp_db):
    _, session = tmp_db
    return UserRepository(session)


@pytest.fixture
def setting_repo(tmp_db):
    _, session = tmp_db
    return SettingRepository(session)


@pytest.fixture
def audit_repo(tmp_db):
    _, session = tmp_db
    return AuditRepository(session)
