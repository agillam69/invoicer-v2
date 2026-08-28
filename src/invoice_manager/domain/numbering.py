"""Document numbering rules (build specification section 17)."""

from __future__ import annotations

import re
from enum import StrEnum

DEFAULT_PADDING = 4


class SequenceType(StrEnum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CREDIT_NOTE = "credit_note"


DEFAULT_PREFIXES: dict[SequenceType, str] = {
    SequenceType.INVOICE: "INV",
    SequenceType.RECEIPT: "RCT",
    SequenceType.CREDIT_NOTE: "CN",
}


class NumberingError(ValueError):
    """Raised when a number cannot be produced or safely interpreted."""


class UnsafeNumberError(NumberingError):
    """Raised for legacy numbers that must be quarantined, e.g. ``0001-1``."""


def format_number(prefix: str, value: int, *, padding: int = DEFAULT_PADDING) -> str:
    """Build a canonical number such as ``INV-0001``."""
    if value < 1:
        raise NumberingError("Document numbers start at 1.")
    if padding < 1:
        raise NumberingError("Padding must be at least 1.")
    return f"{prefix}-{value:0{padding}d}"


def parse_number(canonical: str, *, prefix: str) -> int:
    """Read the numeric part of a canonical number."""
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", canonical.strip().upper())
    if match is None:
        raise NumberingError(f"{canonical!r} is not a {prefix} number.")
    return int(match.group(1))


def normalise_imported_number(raw: str, *, prefix: str, padding: int = DEFAULT_PADDING) -> str:
    """Normalise an approved legacy variant into canonical form.

    Accepts ``0001``, ``1``, ``INV001``, ``INV-0001`` and ``INV 0001``. Suffixed
    variants such as ``0001-1`` are rejected so the importer can quarantine them
    rather than silently merging them into a real invoice.
    """
    text = (raw or "").strip().upper().replace("_", "-")
    if not text:
        raise UnsafeNumberError("Legacy number is blank.")

    body = re.sub(rf"^{re.escape(prefix)}[\s\-]*", "", text)
    if not re.fullmatch(r"\d+", body):
        raise UnsafeNumberError(
            f"{raw!r} is not a recognised {prefix} number and must be reviewed."
        )
    return format_number(prefix, int(body), padding=padding)
