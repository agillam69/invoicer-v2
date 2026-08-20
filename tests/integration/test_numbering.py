from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from invoice_manager.application.numbering import NumberingService
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
    assert session.query(NumberSequence).count() == 2
