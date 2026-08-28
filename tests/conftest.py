from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from invoice_manager.persistence.database import (
    create_database,
    initialise_database,
    session_factory,
)


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_database("sqlite:///:memory:")
    initialise_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine):
    factory = session_factory(engine)
    with factory() as value:
        yield value
