"""Numbering tests (FR-INV-003, FR-RCT-002, FR-SET-003)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from invoice_manager.application.numbering_service import NumberingService
from invoice_manager.domain.numbering import (
    NumberingError,
    SequenceType,
    UnsafeNumberError,
    format_number,
    normalise_imported_number,
    parse_number,
)
from invoice_manager.persistence.database import create_session_factory, seed_reference_data
from invoice_manager.persistence.models import NumberSequence

pytestmark = [pytest.mark.integration]


def test_invoice_numbers_are_sequential_and_padded(session: Session) -> None:
    numbering = NumberingService(session)

    numbers = [numbering.reserve(SequenceType.INVOICE) for _ in range(3)]

    assert numbers == ["INV-0001", "INV-0002", "INV-0003"]


def test_each_document_type_has_its_own_sequence(session: Session) -> None:
    numbering = NumberingService(session)

    assert numbering.reserve(SequenceType.INVOICE) == "INV-0001"
    assert numbering.reserve(SequenceType.RECEIPT) == "RCT-0001"
    assert numbering.reserve(SequenceType.CREDIT_NOTE) == "CN-0001"
    assert numbering.reserve(SequenceType.RECEIPT) == "RCT-0002"


def test_reserved_number_is_never_reused_after_rollback(session: Session) -> None:
    """A cancelled issue consumes its number instead of handing it out twice."""
    numbering = NumberingService(session)
    first = numbering.reserve(SequenceType.INVOICE)
    session.commit()

    second = numbering.reserve(SequenceType.INVOICE)
    session.rollback()

    third = NumberingService(session).reserve(SequenceType.INVOICE)
    assert (first, second) == ("INV-0001", "INV-0002")
    assert third != first


def test_committed_reservation_survives_a_new_session(session: Session) -> None:
    numbering = NumberingService(session)
    numbering.reserve(SequenceType.INVOICE)
    session.commit()

    bind = session.get_bind()
    other_session = create_session_factory(bind)()  # type: ignore[arg-type]
    try:
        assert NumberingService(other_session).reserve(SequenceType.INVOICE) == "INV-0002"
    finally:
        other_session.close()


def test_unique_constraint_protects_against_duplicate_sequences(session: Session) -> None:
    session.add(NumberSequence(sequence_type="invoice", prefix="INV", next_value=1, padding=4))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    seed_reference_data(session)


def test_prefix_and_padding_are_configurable(session: Session) -> None:
    numbering = NumberingService(session)

    settings = numbering.configure(SequenceType.INVOICE, prefix="tax", padding=6)

    assert (settings.prefix, settings.padding) == ("TAX", 6)
    assert numbering.reserve(SequenceType.INVOICE) == "TAX-000001"


def test_next_number_cannot_move_backwards(session: Session) -> None:
    numbering = NumberingService(session)
    numbering.reserve(SequenceType.INVOICE)
    numbering.reserve(SequenceType.INVOICE)

    with pytest.raises(NumberingError):
        numbering.configure(SequenceType.INVOICE, next_value=2)


@pytest.mark.parametrize("padding", [0, -1])
def test_invalid_padding_is_rejected(session: Session, padding: int) -> None:
    with pytest.raises(NumberingError):
        NumberingService(session).configure(SequenceType.INVOICE, padding=padding)


def test_next_invoice_after_migration_is_0005(session: Session) -> None:
    numbering = NumberingService(session)

    numbering.ensure_at_least(SequenceType.INVOICE, 5)

    assert numbering.peek(SequenceType.INVOICE).next_value == 5
    assert numbering.reserve(SequenceType.INVOICE) == "INV-0005"


def test_ensure_at_least_never_lowers_a_sequence(session: Session) -> None:
    numbering = NumberingService(session)
    numbering.configure(SequenceType.INVOICE, next_value=10)

    numbering.ensure_at_least(SequenceType.INVOICE, 5)

    assert numbering.peek(SequenceType.INVOICE).next_value == 10


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0001", "INV-0001"),
        ("1", "INV-0001"),
        ("INV001", "INV-0001"),
        ("INV-0001", "INV-0001"),
        ("inv 0001", "INV-0001"),
        ("INV_0002", "INV-0002"),
    ],
)
def test_approved_legacy_variants_normalise(raw: str, expected: str) -> None:
    assert normalise_imported_number(raw, prefix="INV") == expected


@pytest.mark.parametrize("raw", ["0001-1", "0001-A", "ERROR", "", "INV-0001-1", "0001/1"])
def test_unsafe_legacy_numbers_are_quarantined(raw: str) -> None:
    with pytest.raises(UnsafeNumberError):
        normalise_imported_number(raw, prefix="INV")


def test_canonical_format_and_parse_round_trip() -> None:
    assert format_number("RCT", 4) == "RCT-0004"
    assert parse_number("RCT-0004", prefix="RCT") == 4
    with pytest.raises(NumberingError):
        format_number("INV", 0)
    with pytest.raises(NumberingError):
        parse_number("INV-0001", prefix="RCT")
