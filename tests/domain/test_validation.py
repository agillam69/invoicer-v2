from datetime import date

from invoice_manager.domain.validation import (
    format_date,
    is_non_empty,
    normalise_abn,
    parse_amount,
    parse_date,
    validate_email,
)


def test_parse_slash_date():
    assert parse_date("25/06/2026") == date(2026, 6, 25)


def test_parse_iso_date():
    assert parse_date("2026-06-25") == date(2026, 6, 25)


def test_parse_invalid_date():
    assert parse_date("not a date") is None


def test_parse_date_from_date_object():
    d = date(2026, 6, 25)
    assert parse_date(d) == d


def test_parse_empty_date():
    assert parse_date(None) is None
    assert parse_date("") is None


def test_format_date():
    assert format_date(date(2026, 6, 25)) == "25/06/2026"


def test_parse_amount_cents():
    assert parse_amount("12.34") == 1234
    assert parse_amount("$1,234.56") == 123456


def test_parse_amount_invalid():
    assert parse_amount("abc") is None


def test_validate_email():
    assert validate_email("a@b.com") is True
    assert validate_email("not-an-email") is False


def test_normalise_abn():
    assert normalise_abn("12 345 678 901") == "12345678901"


def test_is_non_empty():
    assert is_non_empty("hello") is True
    assert is_non_empty("  ") is False
    assert is_non_empty(None) is False
