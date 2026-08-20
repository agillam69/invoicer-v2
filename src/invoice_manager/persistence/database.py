from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, insert
from sqlalchemy.orm import Session, sessionmaker

from invoice_manager.persistence.models import Base, NumberSequence

SEQUENCE_SEEDS = (
    {"sequence_type": "invoice", "prefix": "INV-", "next_value": 1, "padding": 4},
    {"sequence_type": "receipt", "prefix": "RCT-", "next_value": 1, "padding": 4},
    {"sequence_type": "credit_note", "prefix": "CN-", "next_value": 1, "padding": 4},
)


def create_database(url: str = "sqlite:///invoicer.sqlite3") -> Engine:
    connect_args = {"timeout": 30} if url.startswith("sqlite:") else {}
    engine = create_engine(url, future=True, connect_args=connect_args)
    if engine.url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def initialise_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for seed in SEQUENCE_SEEDS:
            connection.execute(insert(NumberSequence).values(**seed).prefix_with("OR IGNORE"))


def migrate_database(engine: Engine) -> None:
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    initialise_database_sequences(engine)


def initialise_database_sequences(engine: Engine) -> None:
    with engine.begin() as connection:
        for seed in SEQUENCE_SEEDS:
            connection.execute(insert(NumberSequence).values(**seed).prefix_with("OR IGNORE"))


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"
