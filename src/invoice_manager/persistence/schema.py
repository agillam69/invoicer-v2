"""Running Alembic migrations from application code."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str) -> None:
    """Bring a new or existing database up to the latest schema."""
    command.upgrade(alembic_config(database_url), "head")


def head_revision(database_url: str) -> str | None:
    script = ScriptDirectory.from_config(alembic_config(database_url))
    return script.get_current_head()


def current_revision(engine: Engine) -> str | None:
    """The revision stamped in the database, or ``None`` when unstamped."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def is_up_to_date(engine: Engine, database_url: str) -> bool:
    return current_revision(engine) == head_revision(database_url)
