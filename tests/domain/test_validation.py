from datetime import date

import pytest

from invoice_manager.domain.validation import (
    csv_safe,
    display_date,
    parse_and_store_date,
    parse_typed_date,
    preserve_leading_zero,
    validate_abn,
    validate_email,
    validate_filename,
    validate_relative_path,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("25/06/2026", date(2026, 6, 25)),
        ("25-06-2026", date(2026, 6, 25)),
        ("5/6/26", date(2026, 6, 5)),
        ("2026-06-25", date(2026, 6, 25)),
        ("25 Jun 2026", date(2026, 6, 25)),
        ("25Jun2026", date(2026, 6, 25)),
    ],
)
def test_tolerant_dates(value: str, expected: date) -> None:
    assert parse_typed_date(value) == expected


@pytest.mark.parametrize("value", ["31/02/2026", "not a date", ""])
def test_impossible_or_blank_dates_rejected(value: str) -> None:
    assert parse_typed_date(value) is None


def test_dates_display_and_storage_are_distinct() -> None:
    parsed = parse_typed_date("25Jun2026")
    assert parsed is not None
    assert display_date(parsed) == "25/06/2026"
    assert parse_and_store_date("25/06/2026") == "2026-06-25"


def test_abn_checksum_and_email() -> None:
    assert validate_abn("51 824 753 556")
    assert not validate_abn("12 345 678 901")
    assert validate_email("alex@example.com")
    assert not validate_email("alex@")


def test_safety_and_leading_zero_rules() -> None:
    assert preserve_leading_zero("0001") == "0001"
    assert validate_filename("invoice-0001.pdf")
    assert not validate_filename("../invoice.pdf")
    assert validate_relative_path("invoices/2026/a.pdf")
    assert not validate_relative_path("../a.pdf")
    assert csv_safe("=SUM(A1)") == "'=SUM(A1)"
