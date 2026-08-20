import pytest
from sqlalchemy.exc import IntegrityError

from invoice_manager.application.numbering import NumberingService
from invoice_manager.persistence.models import Invoice, NumberSequence, Receipt


def test_canonical_prefix_padding_and_transactional_rollback(session) -> None:
    service = NumberingService()
    assert service.reserve(session, "invoice") == "INV-0001"
    session.commit()
    assert service.reserve(session, "invoice") == "INV-0002"
    session.rollback()
    assert service.reserve(session, "invoice") == "INV-0002"


def test_numbers_are_never_reused_by_unique_documents(session) -> None:
    service = NumberingService()
    number = service.reserve(session, "invoice")
    session.add(Invoice(canonical_number=number, invoice_date="2026-01-01",
                        due_date="2026-01-15", client_id=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_all_document_sequence_types(session) -> None:
    service = NumberingService()
    assert service.reserve(session, "receipt") == "RCT-0001"
    assert service.reserve(session, "credit_note") == "CN-0001"
    assert session.query(NumberSequence).count() == 2
