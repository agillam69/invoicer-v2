"""Validation and parsing shared by the whole application."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

AU_DATE_FORMAT = "%d/%m/%Y"
ISO_DATE_FORMAT = "%Y-%m-%d"

_ACCEPTED_DATE_FORMATS = (
    AU_DATE_FORMAT,
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d.%m.%Y",
    ISO_DATE_FORMAT,
    "%d%b%Y",
    "%d%b%y",
    "%d %b %Y",
    "%d %B %Y",
)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


class ValidationError(ValueError):
    """Raised when user or imported input is not acceptable."""


def require_text(value: str | None, field_name: str) -> str:
    """Return trimmed text, rejecting blank input for a required field."""
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{field_name} is required.")
    return text


def optional_text(value: str | None) -> str | None:
    """Return trimmed text, or ``None`` when the field is blank."""
    text = (value or "").strip()
    return text or None


def parse_date(value: str, *, field_name: str = "Date") -> date:
    """Parse a typed Australian date, tolerating the common shorthands."""
    text = require_text(value, field_name).replace(",", " ")
    text = re.sub(r"\s+", " ", text).strip()
    for date_format in _ACCEPTED_DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ValidationError(f"{field_name} must be a real date such as 25/06/2026.")


def format_date_au(value: date | None) -> str:
    """Format a date for the screen or a document; blank stays blank."""
    return value.strftime(AU_DATE_FORMAT) if value is not None else ""


def format_date_iso(value: date | None) -> str:
    """Format a date for storage and exports."""
    return value.strftime(ISO_DATE_FORMAT) if value is not None else ""


def validate_email(value: str, *, field_name: str = "Email") -> str:
    """Validate an email address, returning it lower-cased."""
    text = require_text(value, field_name)
    if not _EMAIL_PATTERN.match(text):
        raise ValidationError(f"{field_name} must be a valid email address.")
    return text.lower()


def normalise_abn(value: str) -> str:
    """Strip spaces from an ABN, keeping its digits."""
    return re.sub(r"\s+", "", value or "")


def is_valid_abn(value: str) -> bool:
    """Check an ABN using the ATO weighted-modulus-89 algorithm."""
    digits = normalise_abn(value)
    if len(digits) != 11 or not digits.isdigit():
        return False
    weighted = [int(digit) for digit in digits]
    weighted[0] -= 1
    total = sum(digit * weight for digit, weight in zip(weighted, _ABN_WEIGHTS, strict=True))
    return total % 89 == 0


def validate_abn(value: str, *, field_name: str = "ABN") -> str:
    """Validate an ABN and return it in ``NN NNN NNN NNN`` display form."""
    digits = normalise_abn(value)
    if not is_valid_abn(digits):
        raise ValidationError(f"{field_name} must be a valid 11-digit ABN.")
    return f"{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"


def safe_filename(value: str, *, field_name: str = "File name") -> str:
    """Reduce a supplied name to a safe Windows filename."""
    text = require_text(value, field_name)
    text = unicodedata.normalize("NFKC", text).replace("\n", " ").strip()
    candidate = _UNSAFE_FILENAME_CHARS.sub("_", text).strip(" .")
    if not candidate or set(candidate) <= {"_"}:
        raise ValidationError(f"{field_name} does not contain any usable characters.")
    stem = candidate.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        candidate = f"_{candidate}"
    return candidate[:180]


def safe_relative_path(value: str, *, field_name: str = "Path") -> str:
    """Validate a managed-storage relative path, rejecting traversal."""
    text = require_text(value, field_name).replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ValidationError(f"{field_name} must be a relative path.")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValidationError(f"{field_name} must stay inside managed storage.")
    if not parts:
        raise ValidationError(f"{field_name} is required.")
    return "/".join(safe_filename(part, field_name=field_name) for part in parts)


def csv_safe_value(value: str | None) -> str:
    """Neutralise spreadsheet formula injection in exported text."""
    text = "" if value is None else str(value)
    if text.startswith(_CSV_INJECTION_PREFIXES):
        return f"'{text}"
    return text


def preserve_leading_zeros(value: str, *, width: int) -> str:
    """Keep a numeric reference such as ``0001`` padded to ``width``."""
    text = (value or "").strip()
    if not text.isdigit():
        return text
    return text.zfill(width)
