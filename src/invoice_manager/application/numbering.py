from __future__ import annotations

import threading

from sqlalchemy import update
from sqlalchemy.orm import Session

from invoice_manager.persistence.clock import utc_now
from invoice_manager.persistence.models import NumberSequence

SEQUENCES = {
    "invoice": ("INV-", 4),
    "receipt": ("RCT-", 4),
    "credit_note": ("CN-", 4),
}
_reservation_lock = threading.Lock()


class NumberingService:
    """Reserves canonical numbers within the caller's transaction."""

    def reserve(self, session: Session, sequence_type: str) -> str:
        with _reservation_lock:
            return self._reserve(session, sequence_type)

    def _reserve(self, session: Session, sequence_type: str) -> str:
        try:
            prefix, padding = SEQUENCES[sequence_type]
        except KeyError as exc:
            raise ValueError(f"unknown sequence type: {sequence_type}") from exc
        result = session.execute(
            update(NumberSequence)
            .where(NumberSequence.sequence_type == sequence_type)
            .values(next_value=NumberSequence.next_value + 1, updated_at=utc_now())
            .returning(NumberSequence.next_value)
        )
        next_value = result.scalar_one_or_none()
        result.close()
        if next_value is None:
            new_sequence = NumberSequence(
                sequence_type=sequence_type, prefix=prefix, next_value=2, padding=padding
            )
            session.add(new_sequence)
            session.flush()
            value = 1
        else:
            value = next_value - 1
        return f"{prefix}{value:0{padding}d}"
