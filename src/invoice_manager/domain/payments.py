"""Payment rules (build specification section 21)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


class PaymentError(ValueError):
    """Raised when a payment breaks a financial rule."""


@dataclass(frozen=True, slots=True)
class PaymentRecord:
    """The subset of a stored payment the domain needs for calculations."""

    amount_cents: int
    payment_date: date | None = None
    reversed_: bool = False


def valid_payment_total(payments: Iterable[PaymentRecord]) -> int:
    """Total of payments that have not been reversed."""
    return sum(payment.amount_cents for payment in payments if not payment.reversed_)


def validate_payment_amount(amount_cents: int) -> None:
    """A payment must be a positive amount; reversal is used to undo one."""
    if amount_cents <= 0:
        raise PaymentError("Payment amount must be greater than zero.")


def is_overpayment(amount_cents: int, balance_cents: int) -> bool:
    """Whether recording ``amount_cents`` would exceed the invoice balance."""
    return amount_cents > balance_cents
