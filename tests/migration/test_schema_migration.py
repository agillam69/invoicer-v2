from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from invoice_manager.persistence.database import create_database
from invoice_manager.persistence.models import Base


def test_head_matches_models_metadata(tmp_path: Path) -> None:
    engine = create_database(f"sqlite:///{(tmp_path / 'migration.sqlite3').as_posix()}")
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[2] / "src/invoice_manager/persistence/migrations"),
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        migration_context = MigrationContext.configure(connection)
        assert compare_metadata(migration_context, Base.metadata) == []
    engine.dispose()
