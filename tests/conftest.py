"""Shared fixtures: every test gets its own temporary database and data root."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from invoice_manager.config import AppPaths
from invoice_manager.persistence.database import (
    create_engine_for_path,
    create_session_factory,
    seed_reference_data,
)
from invoice_manager.persistence.schema import upgrade_to_head

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Argon2 parameters tuned for test speed only; the application uses the defaults.
TEST_HASHER = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    paths = AppPaths.resolve(tmp_path / "InvoiceReceiptManager")
    paths.ensure_directories()
    return paths


@pytest.fixture
def engine(app_paths: AppPaths) -> Iterator[Engine]:
    upgrade_to_head(app_paths.database_url())
    database_engine = create_engine_for_path(app_paths.database_path)
    try:
        yield database_engine
    finally:
        database_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    session_factory = create_session_factory(engine)
    database_session = session_factory()
    seed_reference_data(database_session)
    database_session.commit()
    try:
        yield database_session
    finally:
        database_session.close()


@pytest.fixture
def hasher() -> PasswordHasher:
    return TEST_HASHER
