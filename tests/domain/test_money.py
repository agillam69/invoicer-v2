from decimal import Decimal

from invoice_manager.domain.money import Money, format_money, from_cents, to_cents


def test_to_cents_int():
    assert to_cents(123) == 123


def test_to_cents_string_with_symbol_and_comma():
    assert to_cents("$1,234.56") == 123456


def test_to_cents_empty_returns_zero():
    assert to_cents(None) == 0
    assert to_cents("") == 0


def test_from_cents():
    assert from_cents(1234) == Decimal("12.34")


def test_format_money():
    assert format_money(1234) == "$12.34"


def test_money_arithmetic():
    assert (Money("10.00") + Money("5.50")).cents == 1550
    assert (Money("10.00") - Money("5.50")).cents == 450


def test_money_comparison():
    assert Money("1.00") < Money("2.00")
    assert Money("2.00") == Money("2.00")


def test_money_zero():
    assert Money.zero().cents == 0
