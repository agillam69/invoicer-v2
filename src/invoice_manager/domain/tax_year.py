"""Configurable financial-year helpers."""

from __future__ import annotations

import calendar
from datetime import date


class TaxYear:
    """Represents a configurable financial/tax year."""

    def __init__(self, start_month: int = 7) -> None:
        if not 1 <= start_month <= 12:
            raise ValueError("start_month must be between 1 and 12")
        self.start_month = start_month

    def start_of_year(self, year: int) -> date:
        return date(year, self.start_month, 1)

    def for_date(self, d: date | None = None) -> str:
        """Return a label like '2025-2026' for the given date."""
        d = d or date.today()
        start = self.start_of_year(d.year)
        y1 = d.year - 1 if d < start else d.year
        y2 = y1 if self.start_month == 1 else y1 + 1
        return f"{y1}-{y2}"

    def current(self) -> str:
        return self.for_date(date.today())

    def dates(self, label: str | None = None) -> tuple[date, date]:
        """Return (start, end) date range for a financial-year label."""
        if label:
            clean = label.replace("/", "-")
            parts = [p for p in clean.split("-") if p.isdigit()]
            y1 = int(parts[0]) if parts else date.today().year
            y2 = int(parts[1]) if len(parts) > 1 else y1
        else:
            current = self.current().split("-")
            y1 = int(current[0])
            y2 = int(current[1])

        start = self.start_of_year(y1)
        end_year = y2 if self.start_month > 1 else y1
        end_month = self.start_month - 1
        if end_month == 0:
            end_month = 12
        end_day = calendar.monthrange(end_year, end_month)[1]
        end = date(end_year, end_month, end_day)
        return start, end
