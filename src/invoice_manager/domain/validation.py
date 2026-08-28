"""Tolerant parsing and validation helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from re import Pattern

# Australian date formats understood by parse_date.
_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%d%b%Y",
]

_EMAIL_RE: Pattern[str] = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def parse_date(value: str | date | None) -> date | None:
    """Parse a flexible date string into a date object.

    Returns None if the input is empty or cannot be parsed.
    """
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def format_date(value: date | str | None) -> str:
    """Return DD/MM/YYYY for display, or '' for None/empty."""
    if value is None or value == "":
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def parse_amount(value: str | float | int | None) -> int | None:
    """Parse an amount string into integer cents.

    Returns None if the input cannot be parsed as a number.
    """
    from invoice_manager.domain.money import to_cents

    if value is None or value == "":
        return None
    try:
        return to_cents(value)
    except Exception:
        return None


def validate_email(value: str | None) -> bool:
    """Return True if value looks like a valid email address."""
    if value is None:
        return False
    return bool(_EMAIL_RE.match(value.strip()))


def normalise_abn(value: str | None) -> str:
    """Return an ABN with whitespace removed, or empty string."""
    if value is None:
        return ""
    return re.sub(r"\s+", "", value.strip())


def is_non_empty(value: str | None) -> bool:
    return value is not None and value.strip() != ""
