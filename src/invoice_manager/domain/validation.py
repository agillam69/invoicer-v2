"""Validated Australian inputs and tolerant legacy date parsing."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path

_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    "%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
    "%b %d %Y", "%B %d %Y", "%d%b%Y", "%d%b%y",
    "%d/%b/%Y", "%d-%b-%Y", "%d.%m.%Y", "%d.%m.%y",
)


def parse_typed_date(value: str) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = re.sub(r"\s+", " ", value.strip())
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def display_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def storage_date(value: date) -> str:
    return value.isoformat()


def parse_and_store_date(value: str) -> str:
    parsed = parse_typed_date(value)
    if parsed is None:
        raise ValueError("invalid date")
    return storage_date(parsed)


def display_from_storage(value: str) -> str:
    parsed = parse_typed_date(value)
    return "" if parsed is None else display_date(parsed)


def validate_abn(value: str) -> bool:
    digits = re.sub(r"\s+", "", value or "")
    if len(digits) != 11 or not digits.isdigit() or len(set(digits)) == 1:
        return False
    weights = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    first = int(digits[0]) - 1
    total = first * weights[0] + sum(int(d) * w for d, w in zip(digits[1:], weights[1:]))
    return total % 89 == 0


def validate_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


def preserve_leading_zero(value: str) -> str:
    return str(value).strip()


def validate_filename(value: str) -> bool:
    if not value or value in {".", ".."} or Path(value).name != value:
        return False
    if any(char in value for char in '<>:"/\\|?*') or value.endswith((" ", ".")):
        return False
    return value.upper() not in {"CON", "PRN", "AUX", "NUL"} and not re.fullmatch(
        r"(COM|LPT)[1-9]", value.upper()
    )


def validate_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and "\x00" not in value


def csv_safe(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_safe_row(values: list[str]) -> list[str]:
    return [csv_safe(value) for value in values]


def csv_safe_text(rows: list[list[str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerows(csv_safe_row(row) for row in rows)
    return stream.getvalue()
