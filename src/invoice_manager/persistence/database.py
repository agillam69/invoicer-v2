"""Engine and session management.

Foreign keys are enforced on every connection, which SQLite does not do by
default.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from invoice_manager.domain.numbering import DEFAULT_PADDING, DEFAULT_PREFIXES, SequenceType
from invoice_manager.persistence.models import Base, BusinessProfile, NumberSequence


def _configure_connection(dbapi_connection: Any, _record: Any) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
    finally:
        cursor.close()


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine with the application's SQLite pragmas applied."""
    engine = create_engine(database_url, echo=echo, future=True)
    event.listen(engine, "connect", _configure_connection)
    return engine


def create_engine_for_path(database_path: Path, *, echo: bool = False) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_database_engine(f"sqlite+pysqlite:///{database_path}", echo=echo)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a unit of work in one transaction, rolling back on any error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_schema(engine: Engine) -> None:
    """Create the schema directly; Alembic owns upgrades of existing data."""
    Base.metadata.create_all(engine)


def seed_reference_data(session: Session) -> None:
    """Insert the number sequences and business profile a new database needs."""
    for sequence_type in SequenceType:
        existing = session.get(NumberSequence, sequence_type.value)
        if existing is None:
            session.add(
                NumberSequence(
                    sequence_type=sequence_type.value,
                    prefix=DEFAULT_PREFIXES[sequence_type],
                    next_value=1,
                    padding=DEFAULT_PADDING,
                )
            )
    current_profile = session.scalars(
        select(BusinessProfile).where(BusinessProfile.is_current.is_(True))
    ).first()
    if current_profile is None:
        session.add(
            BusinessProfile(
                business_name="Alexander Gillam",
                gst_registered=False,
                gst_rate=Decimal("0.0000"),
                currency_code="AUD",
                financial_year_start_month=7,
                default_terms_days=14,
                is_current=True,
            )
        )
