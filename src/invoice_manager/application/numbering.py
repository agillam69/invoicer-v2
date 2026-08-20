from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from invoice_manager.persistence.models import NumberSequence

SEQUENCES = {
    "invoice": ("INV-", 4),
    "receipt": ("RCT-", 4),
    "credit_note": ("CN-", 4),
}


class NumberingService:
    """Reserves canonical numbers within the caller's transaction."""

    def reserve(self, session: Session, sequence_type: str) -> str:
        try:
            prefix, padding = SEQUENCES[sequence_type]
        except KeyError as exc:
            raise ValueError(f"unknown sequence type: {sequence_type}") from exc
        sequence = session.scalar(
            select(NumberSequence)
            .where(NumberSequence.sequence_type == sequence_type)
            .with_for_update()
        )
        if sequence is None:
            sequence = NumberSequence(sequence_type=sequence_type, prefix=prefix,
                                      next_value=1, padding=padding)
            session.add(sequence)
            session.flush()
        value = sequence.next_value
        sequence.next_value += 1
        sequence.updated_at = datetime.utcnow()
        session.flush()
        return f"{sequence.prefix}{value:0{sequence.padding}d}"
