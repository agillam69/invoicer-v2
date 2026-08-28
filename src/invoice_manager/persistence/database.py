"""Database engine, session management, and schema creation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from invoice_manager.persistence.models import Base


class Database:
    """Manages the SQLite database path, engine, and sessions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = self._create_engine(self.db_path)
        self._session_factory = sessionmaker(bind=self._engine)

    @staticmethod
    def _create_engine(path: Path) -> Engine:
        engine = create_engine(
            f"sqlite:///{path}",
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(
            dbapi_conn: Any,
            connection_record: object,  # noqa: ARG001
        ) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    def create_schema(self) -> None:
        """Create all tables if they do not exist."""
        Base.metadata.create_all(self._engine)

    def drop_schema(self) -> None:
        """Drop all tables.  Useful for tests only."""
        Base.metadata.drop_all(self._engine)

    def new_session(self) -> Session:
        return self._session_factory()

    @property
    def engine(self) -> Engine:
        return self._engine
