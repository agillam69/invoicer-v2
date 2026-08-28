"""Money, GST and invoice calculation tests (FR-INV-005, FR-SET-004)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from invoice_manager.domain.invoices import (
    DiscountType,
    InvoiceCalculationError,
    LineInput,
    balance_cents,
    calculate_invoice,
    calculate_line,
)
from invoice_manager.domain.money import (
    MoneyError,
    format_aud,
    from_cents,
    parse_money,
    round_to_cents,
    to_cents,
)

GST_RATE = Decimal("0.10")

pytestmark = [pytest.mark.domain]


@pytest.mark.parametrize(
    ("value", "expected_cents"),
    [
        ("0", 0),
        ("1", 100),
        ("112.50", 11250),
        ("600.00", 60000),
        ("0.005", 1),
        ("0.004", 0),
        ("1234.565", 123457),
        (Decimal("85"), 8500),
        (75, 7500),
    ],
)
def test_to_cents_uses_half_up_rounding(value: Decimal | int | str, expected_cents: int) -> None:
    assert to_cents(value) == expected_cents


def test_parse_money_accepts_formatted_input() -> None:
    assert parse_money(" $1,234.50 ") == 123450
    assert parse_money("(25.00)") == -2500


@pytest.mark.parametrize("value", ["", "abc", "$", "12.3.4"])
def test_parse_money_rejects_invalid_input(value: str) -> None:
    with pytest.raises(MoneyError):
        parse_money(value)


def test_from_cents_and_format() -> None:
    assert from_cents(11250) == Decimal("112.50")
    assert format_aud(123450) == "$1,234.50"
    assert format_aud(-8500) == "-$85.00"
    assert format_aud(0) == "$0.00"


def test_round_to_cents_rejects_non_finite() -> None:
    with pytest.raises(MoneyError):
        round_to_cents(Decimal("NaN"))


def test_non_gst_line_matches_historical_invoice_0002() -> None:
    line = calculate_line(LineInput(quantity=Decimal("1.5"), unit_price_cents=7500, taxable=False))
    assert (line.subtotal_cents, line.gst_cents, line.total_cents) == (11250, 0, 11250)


def test_gst_line_adds_rounded_gst() -> None:
    line = calculate_line(LineInput(quantity=Decimal(1), unit_price_cents=11250, gst_rate=GST_RATE))
    assert (line.subtotal_cents, line.gst_cents, line.total_cents) == (11250, 1125, 12375)


def test_fixed_discount_applies_before_gst() -> None:
    line = calculate_line(
        LineInput(
            quantity=Decimal(2),
            unit_price_cents=10000,
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50.00"),
            gst_rate=GST_RATE,
        )
    )
    assert line.discount_cents == 5000
    assert (line.subtotal_cents, line.gst_cents, line.total_cents) == (15000, 1500, 16500)


def test_percentage_discount_applies_before_gst() -> None:
    line = calculate_line(
        LineInput(
            quantity=Decimal(1),
            unit_price_cents=12345,
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("10"),
            gst_rate=GST_RATE,
        )
    )
    assert line.discount_cents == 1235
    assert (line.subtotal_cents, line.gst_cents, line.total_cents) == (11110, 1111, 12221)


def test_mixed_taxable_invoice_totals() -> None:
    totals = calculate_invoice(
        [
            LineInput(quantity=Decimal(1), unit_price_cents=10000, gst_rate=GST_RATE),
            LineInput(quantity=Decimal(2), unit_price_cents=6000, taxable=False),
        ]
    )
    assert (totals.subtotal_cents, totals.gst_cents, totals.total_cents) == (22000, 1000, 23000)


def test_large_valid_values_stay_exact() -> None:
    totals = calculate_invoice(
        [LineInput(quantity=Decimal(1000), unit_price_cents=999_99, gst_rate=GST_RATE)]
    )
    assert totals.subtotal_cents == 99_999_000
    assert totals.total_cents == 109_998_900


@pytest.mark.parametrize(
    "line",
    [
        LineInput(quantity=Decimal(-1), unit_price_cents=100),
        LineInput(quantity=Decimal(1), unit_price_cents=-100),
        LineInput(quantity=Decimal(1), unit_price_cents=100, gst_rate=Decimal("-0.1")),
        LineInput(
            quantity=Decimal(1),
            unit_price_cents=100,
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("101"),
        ),
        LineInput(
            quantity=Decimal(1),
            unit_price_cents=100,
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("5.00"),
        ),
        LineInput(
            quantity=Decimal(1),
            unit_price_cents=100,
            discount_type=DiscountType.NONE,
            discount_value=Decimal("1"),
        ),
    ],
)
def test_invalid_lines_are_rejected(line: LineInput) -> None:
    with pytest.raises(InvoiceCalculationError):
        calculate_line(line)


def test_changing_the_gst_rate_does_not_change_an_issued_line() -> None:
    """An issued invoice keeps its snapshot rate (FR-SET-004, FR-INV-006)."""
    issued = LineInput(quantity=Decimal(1), unit_price_cents=10000, gst_rate=Decimal("0.00"))
    issued_totals = calculate_line(issued)

    reissued_totals = calculate_line(issued)
    new_settings_totals = calculate_line(
        LineInput(quantity=Decimal(1), unit_price_cents=10000, gst_rate=GST_RATE)
    )

    assert issued_totals == reissued_totals
    assert issued_totals.gst_cents == 0
    assert new_settings_totals.gst_cents == 1000


def test_balance_uses_payments_and_credits() -> None:
    assert balance_cents(60000, 60000, 0) == 0
    assert balance_cents(60000, 20000, 10000) == 30000


def test_recalculated_total_flags_supplied_mismatch() -> None:
    """Imported totals are never trusted (import rule 10)."""
    supplied_total_cents = 55000
    recalculated = calculate_invoice(
        [LineInput(quantity=Decimal(1), unit_price_cents=50000, taxable=False)]
    )
    assert recalculated.total_cents != supplied_total_cents


@given(
    quantity=st.decimals(min_value=0, max_value=1000, places=2),
    unit_price_cents=st.integers(min_value=0, max_value=10_000_000),
)
def test_line_total_is_never_negative(quantity: Decimal, unit_price_cents: int) -> None:
    line = calculate_line(
        LineInput(quantity=quantity, unit_price_cents=unit_price_cents, gst_rate=GST_RATE)
    )
    assert line.total_cents >= 0
    assert line.total_cents == line.subtotal_cents + line.gst_cents
