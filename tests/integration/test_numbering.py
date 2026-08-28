from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from invoice_manager.application.numbering import NumberingService
from invoice_manager.persistence.database import (
    create_database,
    initialise_database,
    session_factory,
)
from invoice_manager.persistence.models import Client, Invoice, NumberSequence


def test_canonical_prefix_padding_and_transactional_rollback(session) -> None:
    service = NumberingService()
    assert service.reserve(session, "invoice") == "INV-0001"
    session.commit()
    assert service.reserve(session, "invoice") == "INV-0002"
    session.rollback()
    assert service.reserve(session, "invoice") == "INV-0002"


def test_numbers_are_never_reused_by_unique_documents(session) -> None:
    service = NumberingService()
    client = Client(display_name="Client")
    session.add(client)
    session.flush()
    number = service.reserve(session, "invoice")
    session.add(
        Invoice(
            canonical_number=number,
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 15),
            client_id=client.id,
        )
    )
    session.commit()
    session.add(
        Invoice(
            canonical_number=number,
            invoice_date=date(2026, 1, 2),
            due_date=date(2026, 1, 16),
            client_id=client.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_all_document_sequence_types(session) -> None:
    service = NumberingService()
    assert service.reserve(session, "receipt") == "RCT-0001"
    assert service.reserve(session, "credit_note") == "CN-0001"
    assert session.query(NumberSequence).count() == 3


def test_concurrent_reservations_are_serialized(tmp_path: Path) -> None:
    database = tmp_path / "concurrent.sqlite3"
    setup_engine = create_database(f"sqlite:///{database.as_posix()}")
    initialise_database(setup_engine)
    setup_engine.dispose()

    def reserve_number() -> str:
        engine = create_database(f"sqlite:///{database.as_posix()}")
        try:
            with session_factory(engine)() as value:
                number = NumberingService().reserve(value, "invoice")
                value.commit()
                return number
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = list(pool.map(lambda _: reserve_number(), range(2)))
    assert sorted(numbers) == ["INV-0001", "INV-0002"]
