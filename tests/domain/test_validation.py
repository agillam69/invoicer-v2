"""Date, ABN, path and export-safety tests (FR-DOC-003)."""

from __future__ import annotations

from datetime import date

import pytest

from invoice_manager.domain.validation import (
    ValidationError,
    csv_safe_value,
    format_date_au,
    format_date_iso,
    is_valid_abn,
    optional_text,
    parse_date,
    preserve_leading_zeros,
    require_text,
    safe_filename,
    safe_relative_path,
    validate_abn,
    validate_email,
)

pytestmark = [pytest.mark.domain]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("25/06/2026", date(2026, 6, 25)),
        ("5/6/26", date(2026, 6, 5)),
        ("25Jun2026", date(2026, 6, 25)),
        ("25 Jun 2026", date(2026, 6, 25)),
        ("25 June 2026", date(2026, 6, 25)),
        ("2026-06-25", date(2026, 6, 25)),
        ("29-04-2026", date(2026, 4, 29)),
        (" 19/06/2026 ", date(2026, 6, 19)),
    ],
)
def test_parse_date_accepts_australian_and_iso_input(text: str, expected: date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "31/02/2026", "2026-13-01", "not a date", "25/6"])
def test_parse_date_rejects_impossible_dates(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_date(text)


def test_date_display_and_storage_formats() -> None:
    assert format_date_au(date(2026, 6, 25)) == "25/06/2026"
    assert format_date_iso(date(2026, 6, 25)) == "2026-06-25"
    assert format_date_au(None) == ""
    assert format_date_iso(None) == ""


def test_blank_required_field_is_rejected_not_shown_as_zero() -> None:
    with pytest.raises(ValidationError):
        require_text("  ", "Client")
    assert optional_text("  ") is None
    assert optional_text(" Chelsea Carr ") == "Chelsea Carr"


@pytest.mark.parametrize("abn", ["51824753556", "51 824 753 556"])
def test_valid_abn_is_accepted(abn: str) -> None:
    assert is_valid_abn(abn) is True
    assert validate_abn(abn) == "51 824 753 556"


@pytest.mark.parametrize("abn", ["51824753557", "1234567890", "abcdefghijk", ""])
def test_invalid_abn_is_rejected(abn: str) -> None:
    assert is_valid_abn(abn) is False
    with pytest.raises(ValidationError):
        validate_abn(abn)


@pytest.mark.parametrize("email", ["alex@example.com.au", "A.Gillam@Example.COM"])
def test_valid_email_is_normalised(email: str) -> None:
    assert validate_email(email) == email.lower()


@pytest.mark.parametrize("email", ["alex", "alex@", "@example.com", "alex@example", "a b@c.com"])
def test_invalid_email_is_rejected(email: str) -> None:
    with pytest.raises(ValidationError):
        validate_email(email)


def test_leading_zeros_are_preserved() -> None:
    assert preserve_leading_zeros("1", width=4) == "0001"
    assert preserve_leading_zeros("0001", width=4) == "0001"
    assert preserve_leading_zeros("0004-R", width=4) == "0004-R"


def test_safe_filename_strips_dangerous_characters() -> None:
    assert safe_filename("INV-0001.pdf") == "INV-0001.pdf"
    assert safe_filename('inv:/\\*?"<>|0001.pdf') == "inv_________0001.pdf"
    assert safe_filename("../../etc/passwd") == "_.._etc_passwd"
    assert safe_filename("CON.pdf") == "_CON.pdf"


@pytest.mark.parametrize("value", ["", "   ", "///", "..."])
def test_safe_filename_rejects_unusable_names(value: str) -> None:
    with pytest.raises(ValidationError):
        safe_filename(value)


def test_safe_relative_path_allows_managed_subfolders() -> None:
    assert safe_relative_path("invoices/2026/INV-0001.pdf") == "invoices/2026/INV-0001.pdf"
    assert safe_relative_path("invoices\\2026\\INV-0001.pdf") == "invoices/2026/INV-0001.pdf"


@pytest.mark.parametrize(
    "value",
    [
        "../secrets.txt",
        "invoices/../../secrets.txt",
        "/etc/passwd",
        "C:/Windows/system32/config",
        "",
    ],
)
def test_safe_relative_path_rejects_traversal(value: str) -> None:
    with pytest.raises(ValidationError):
        safe_relative_path(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=cmd|'/c calc'!A1", "'=cmd|'/c calc'!A1"),
        ("+1234", "'+1234"),
        ("-1234", "'-1234"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("Town and Country Medical", "Town and Country Medical"),
        (None, ""),
    ],
)
def test_csv_export_neutralises_formula_injection(value: str | None, expected: str) -> None:
    assert csv_safe_value(value) == expected
