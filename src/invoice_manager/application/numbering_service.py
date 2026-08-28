"""Transactional number reservation (FR-INV-003, FR-RCT-002, FR-SET-003)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from invoice_manager.domain.numbering import (
    DEFAULT_PADDING,
    DEFAULT_PREFIXES,
    NumberingError,
    SequenceType,
    format_number,
)
from invoice_manager.persistence.models import NumberSequence
from invoice_manager.persistence.repositories import NumberSequenceRepository


@dataclass(frozen=True, slots=True)
class SequenceSettings:
    prefix: str
    next_value: int
    padding: int


class NumberingService:
    """Reserves document numbers inside the caller's transaction.

    A number is consumed as soon as it is reserved, so a rolled-back issue
    attempt never reuses it and never leaves a gap that looks like a lost
    invoice.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._sequences = NumberSequenceRepository(session)

    def _require_sequence(self, sequence_type: SequenceType) -> NumberSequence:
        sequence = self._sequences.get(sequence_type.value)
        if sequence is None:
            sequence = self._sequences.upsert(
                NumberSequence(
                    sequence_type=sequence_type.value,
                    prefix=DEFAULT_PREFIXES[sequence_type],
                    next_value=1,
                    padding=DEFAULT_PADDING,
                )
            )
        return sequence

    def peek(self, sequence_type: SequenceType) -> SequenceSettings:
        sequence = self._require_sequence(sequence_type)
        return SequenceSettings(
            prefix=sequence.prefix, next_value=sequence.next_value, padding=sequence.padding
        )

    def reserve(self, sequence_type: SequenceType) -> str:
        """Reserve and return the next canonical number."""
        sequence = self._require_sequence(sequence_type)
        number = format_number(sequence.prefix, sequence.next_value, padding=sequence.padding)
        sequence.next_value += 1
        sequence.updated_at = datetime.now(UTC)
        self._session.flush()
        return number

    def configure(
        self,
        sequence_type: SequenceType,
        *,
        prefix: str | None = None,
        padding: int | None = None,
        next_value: int | None = None,
    ) -> SequenceSettings:
        """Apply numbering settings, never moving a sequence backwards."""
        sequence = self._require_sequence(sequence_type)
        if prefix is not None:
            cleaned = prefix.strip().upper()
            if not cleaned.isalpha():
                raise NumberingError("Prefix must contain letters only.")
            sequence.prefix = cleaned
        if padding is not None:
            if padding < 1:
                raise NumberingError("Padding must be at least 1.")
            sequence.padding = padding
        if next_value is not None:
            if next_value < sequence.next_value:
                raise NumberingError("The next number cannot be lower than a number already used.")
            sequence.next_value = next_value
        sequence.updated_at = datetime.now(UTC)
        self._session.flush()
        return SequenceSettings(
            prefix=sequence.prefix, next_value=sequence.next_value, padding=sequence.padding
        )

    def ensure_at_least(self, sequence_type: SequenceType, minimum_next_value: int) -> None:
        """Raise the sequence floor, e.g. to ``INV-0005`` after migration."""
        sequence = self._require_sequence(sequence_type)
        if sequence.next_value < minimum_next_value:
            sequence.next_value = minimum_next_value
            sequence.updated_at = datetime.now(UTC)
            self._session.flush()
