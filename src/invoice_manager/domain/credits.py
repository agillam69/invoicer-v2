"""Credit note rules (build specification section 23)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class CreditError(ValueError):
    """Raised when a credit breaks a financial rule."""


@dataclass(frozen=True, slots=True)
class CreditRecord:
    """The subset of a stored credit note the domain needs for calculations."""

    total_cents: int
    void: bool = False


def valid_credit_total(credits: Iterable[CreditRecord]) -> int:
    """Total of credit notes that have not been voided."""
    return sum(credit.total_cents for credit in credits if not credit.void)


def validate_credit_amount(amount_cents: int, remaining_cents: int) -> None:
    """Credits may not silently exceed the amount left on the invoice."""
    if amount_cents <= 0:
        raise CreditError("Credit amount must be greater than zero.")
    if amount_cents > remaining_cents:
        raise CreditError("Credit cannot exceed the remaining invoice amount.")
