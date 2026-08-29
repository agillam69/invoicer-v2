"""Database engine, session management, and schema creation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from invoice_manager.persistence.models import Base


class Database:
    """Manage a local SQLite or configured SQLAlchemy database connection."""

    def __init__(self, database: Path | str | URL) -> None:
        if isinstance(database, Path):
            database.parent.mkdir(parents=True, exist_ok=True)
            url: str | URL = f"sqlite:///{database}"
            self.db_path: Path | None = database
        else:
            url = database
            parsed = make_url(str(database)) if isinstance(database, str) else database
            self.db_path = Path(parsed.database) if parsed.drivername == "sqlite" and parsed.database else None
            if self.db_path is not None:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = self._create_engine(url)
        self._session_factory = sessionmaker(bind=self._engine)

    @staticmethod
    def _create_engine(url: str | URL) -> Engine:
        parsed = make_url(url) if isinstance(url, str) else url
        kwargs: dict[str, Any] = {"echo": False, "future": True, "pool_pre_ping": True}
        if parsed.drivername == "sqlite":
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(url, **kwargs)

        if parsed.drivername == "sqlite":
            @event.listens_for(engine, "connect")
            def _set_sqlite_pragma(
                dbapi_conn: Any,
                connection_record: object,  # noqa: ARG001
            ) -> None:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        return engine

    def test_connection(self) -> None:
        """Open a connection and execute a minimal query."""
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def create_schema(self) -> None:
        """Create all tables if they do not exist."""
        Base.metadata.create_all(self._engine)

    def drop_schema(self) -> None:
        """Drop all tables. Useful for tests only."""
        Base.metadata.drop_all(self._engine)

    def new_session(self) -> Session:
        return self._session_factory()

    @property
    def engine(self) -> Engine:
        return self._engine
