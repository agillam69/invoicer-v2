from decimal import Decimal

import pytest

from invoice_manager.domain.money import (
    MoneyError,
    dollars_to_cents,
    format_aud,
    multiply_quantity,
    parse_aud,
    percentage_amount,
)


def test_money_uses_integer_cents_and_aud_format() -> None:
    assert dollars_to_cents("1,234.56") == 123456
    assert parse_aud("A$12.50") == 1250
    assert format_aud(1250) == "$12.50"
    assert format_aud(-1250) == "-$12.50"
    assert format_aud(1250, "A$") == "A$12.50"


@pytest.mark.parametrize(("value", "expected"), [("1.004", 100), ("1.005", 101), ("0.005", 1)])
def test_cent_rounding_is_half_up(value: str, expected: int) -> None:
    assert dollars_to_cents(value) == expected


def test_float_money_is_rejected() -> None:
    with pytest.raises(MoneyError):
        dollars_to_cents(1.25)  # type: ignore[arg-type]


def test_decimal_intermediate_math_rounds_at_cent() -> None:
    assert multiply_quantity(Decimal("2.5"), 199) == 498
    assert percentage_amount(1001, "10") == 100
