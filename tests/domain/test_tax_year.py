"""Tests for configurable financial-year helpers."""

from __future__ import annotations

from datetime import date

import pytest

from invoice_manager.domain.tax_year import TaxYear


def test_july_start():
    fy = TaxYear(7)
    assert fy.current() in ("2025-2026", "2026-2027")
    start, end = fy.dates("2025-2026")
    assert start == date(2025, 7, 1)
    assert end == date(2026, 6, 30)


def test_january_start():
    fy = TaxYear(1)
    assert fy.for_date(date(2025, 3, 15)) == "2025-2025"
    start, end = fy.dates("2025-2025")
    assert start == date(2025, 1, 1)
    assert end == date(2025, 12, 31)


def test_april_start():
    fy = TaxYear(4)
    start, end = fy.dates("2025-2026")
    assert start == date(2025, 4, 1)
    assert end == date(2026, 3, 31)


def test_invalid_month():
    with pytest.raises(ValueError):
        TaxYear(13)
