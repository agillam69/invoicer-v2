"""
date_utils.py
=============
Date helpers and a DateEntry widget for the Invoice Generator.

Public API
----------
parse_date(text) -> datetime.date | None
    Accept a date in virtually any common format; always return a
    datetime.date (or None if unparseable).

fmt_display(d)  -> str        dd/mm/yyyy  (for screen display)
fmt_storage(d)  -> str        yyyy-mm-dd  (for CSV / internal storage)
fmt_or_blank(v) -> str        dd/mm/yyyy or '' if blank/invalid
storage_to_display(s) -> str  convert yyyy-mm-dd → dd/mm/yyyy
display_to_storage(s) -> str  convert dd/mm/yyyy → yyyy-mm-dd

DateEntry(parent, textvariable, **kw)
    A ttk.Frame subclass containing a 15-char Entry and a small "📅"
    button that opens a lightweight calendar popup.  The StringVar
    stores the date as dd/mm/yyyy for display; callers should use
    display_to_storage() before persisting.
"""

import calendar
import re
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import ttk


# ---------------------------------------------------------------------------
# Recognised input formats (tried in order)
# ---------------------------------------------------------------------------
_INPUT_FORMATS = [
    '%d/%m/%Y',   # 25/06/2026  ← canonical display
    '%d-%m-%Y',   # 25-06-2026
    '%d %m %Y',   # 25 06 2026
    '%d/%m/%y',   # 25/06/26
    '%d-%m-%y',   # 25-06-26
    '%Y-%m-%d',   # 2026-06-25  (ISO / storage)
    '%Y/%m/%d',   # 2026/06/25
    '%d %b %Y',   # 25 Jun 2026
    '%d %B %Y',   # 25 June 2026
    '%b %d %Y',   # Jun 25 2026
    '%B %d %Y',   # June 25 2026
    '%d%b%Y',     # 25Jun2026
    '%d%b%y',     # 25Jun26
    '%d/%b/%Y',   # 25/Jun/2026
    '%d-%b-%Y',   # 25-Jun-2026
    '%d.%m.%Y',   # 25.06.2026
    '%d.%m.%y',   # 25.06.26
]

_DISPLAY_FMT = '%d/%m/%Y'
_STORAGE_FMT = '%Y-%m-%d'


def parse_date(text: str) -> 'date | None':
    """Try to parse *text* as a date using every known format.
    Returns a datetime.date or None."""
    if not text:
        return None
    text = text.strip()
    # Normalise multiple spaces / mixed separators
    text = re.sub(r'\s+', ' ', text)
    for fmt in _INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fmt_display(d) -> str:
    """Format a date object as dd/mm/yyyy."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(_DISPLAY_FMT)


def fmt_storage(d) -> str:
    """Format a date object as yyyy-mm-dd for CSV storage."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(_STORAGE_FMT)


def fmt_or_blank(value: str) -> str:
    """Convert any date string to dd/mm/yyyy display, or return '' if blank/invalid."""
    if not value or not value.strip():
        return ''
    d = parse_date(value.strip())
    return fmt_display(d) if d else value.strip()


def storage_to_display(s: str) -> str:
    """yyyy-mm-dd → dd/mm/yyyy.  Pass-through if already in display format or blank."""
    return fmt_or_blank(s)


def display_to_storage(s: str) -> str:
    """dd/mm/yyyy → yyyy-mm-dd.  Returns '' if blank or unparseable."""
    if not s or not s.strip():
        return ''
    d = parse_date(s.strip())
    return fmt_storage(d) if d else s.strip()


# ---------------------------------------------------------------------------
# Calendar popup
# ---------------------------------------------------------------------------
class _CalendarPopup(tk.Toplevel):
    """Lightweight month-grid calendar for date selection."""

    def __init__(self, parent, initial: 'date | None' = None,
                 callback=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.resizable(False, False)
        self.grab_set()
        self._callback = callback
        self._selected = initial or date.today()
        self._viewing = date(self._selected.year, self._selected.month, 1)
        self._day_btns = []
        self._build()
        self._position(parent)
        self.bind('<Escape>', lambda e: self.destroy())

    def _position(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty() + parent.winfo_height() + 2
        sw = self.winfo_screenwidth()
        w  = self.winfo_reqwidth()
        if px + w > sw:
            px = sw - w - 4
        self.geometry(f'+{px}+{py}')

    def _build(self):
        self._frame = ttk.Frame(self, relief='solid', borderwidth=1)
        self._frame.pack()
        self._nav = ttk.Frame(self._frame)
        self._nav.pack(fill='x')
        ttk.Button(self._nav, text='◀', width=2,
                   command=self._prev_month).pack(side='left', padx=2)
        self._month_lbl = ttk.Label(self._nav, width=14, anchor='center')
        self._month_lbl.pack(side='left', expand=True)
        ttk.Button(self._nav, text='▶', width=2,
                   command=self._next_month).pack(side='right', padx=2)

        self._grid = ttk.Frame(self._frame)
        self._grid.pack(padx=4, pady=(0, 4))
        for col, name in enumerate(('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')):
            ttk.Label(self._grid, text=name, width=3, anchor='center',
                      font=('TkDefaultFont', 8, 'bold')).grid(
                row=0, column=col, padx=1)

        self._render()

    def _render(self):
        for btn in self._day_btns:
            btn.destroy()
        self._day_btns = []
        self._month_lbl.config(
            text=self._viewing.strftime('%b %Y'))
        cal = calendar.monthcalendar(self._viewing.year, self._viewing.month)
        for row_idx, week in enumerate(cal, 1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    lbl = ttk.Label(self._grid, text='', width=3)
                    lbl.grid(row=row_idx, column=col_idx, padx=1, pady=1)
                    self._day_btns.append(lbl)
                else:
                    d = date(self._viewing.year, self._viewing.month, day)
                    is_sel = (d == self._selected)
                    is_today = (d == date.today())
                    style = 'Accent.TButton' if is_sel else (
                        'TButton' if not is_today else 'TButton')
                    fg = 'white' if is_sel else ('blue' if is_today else 'black')
                    btn = tk.Button(
                        self._grid, text=str(day), width=2,
                        relief='flat' if not is_sel else 'sunken',
                        bg='#4472C4' if is_sel else ('#e8f0fe' if is_today else 'SystemButtonFace'),
                        fg=fg,
                        font=('TkDefaultFont', 8),
                        command=lambda _d=d: self._pick(_d))
                    btn.grid(row=row_idx, column=col_idx, padx=1, pady=1)
                    self._day_btns.append(btn)

    def _prev_month(self):
        y, m = self._viewing.year, self._viewing.month
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        self._viewing = date(y, m, 1)
        self._render()

    def _next_month(self):
        y, m = self._viewing.year, self._viewing.month
        m += 1
        if m == 13:
            m, y = 1, y + 1
        self._viewing = date(y, m, 1)
        self._render()

    def _pick(self, d: date):
        self._selected = d
        if self._callback:
            self._callback(d)
        self.destroy()


# ---------------------------------------------------------------------------
# DateEntry widget
# ---------------------------------------------------------------------------
class DateEntry(ttk.Frame):
    """
    A compound widget: [  dd/mm/yyyy entry  ] [📅]

    textvariable stores the date in **dd/mm/yyyy** display format.

    On focus-out and on calendar pick, the value is normalised to
    dd/mm/yyyy regardless of what format the user typed.

    Usage:
        var = tk.StringVar()
        de = DateEntry(parent, textvariable=var)
        de.grid(...)
        # read:  var.get()                    → 'dd/mm/yyyy' or ''
        # store: display_to_storage(var.get()) → 'yyyy-mm-dd' or ''
    """

    def __init__(self, parent, textvariable: tk.StringVar = None,
                 width: int = 12, state: str = 'normal', **kw):
        super().__init__(parent, **kw)
        self._var = textvariable if textvariable is not None else tk.StringVar()
        self._state = state

        self._entry = ttk.Entry(self, textvariable=self._var, width=width,
                                state=state)
        self._entry.pack(side='left')

        if state != 'readonly' and state != 'disabled':
            self._btn = ttk.Button(self, text='📅', width=2,
                                   command=self._open_calendar,
                                   style='Toolbutton')
            self._btn.pack(side='left', padx=(1, 0))
            self._entry.bind('<FocusOut>', self._on_focus_out)
            self._entry.bind('<Return>',  self._on_focus_out)
        else:
            self._btn = None

        # Normalise any existing value (e.g. yyyy-mm-dd coming from storage)
        self._normalise()

    def _normalise(self, *_):
        raw = self._var.get().strip()
        if not raw:
            return
        d = parse_date(raw)
        if d:
            self._var.set(fmt_display(d))

    def _on_focus_out(self, *_):
        self._normalise()

    def _open_calendar(self):
        raw = self._var.get().strip()
        initial = parse_date(raw) if raw else date.today()
        _CalendarPopup(self._entry, initial=initial,
                       callback=self._on_pick)

    def _on_pick(self, d: date):
        self._var.set(fmt_display(d))
        self._entry.focus_set()

    # Proxy useful Entry/StringVar methods
    def get(self) -> str:
        return self._var.get()

    def set(self, value: str):
        self._var.set(value)
        self._normalise()

    def get_storage(self) -> str:
        """Return the date as yyyy-mm-dd for CSV storage, or ''."""
        return display_to_storage(self._var.get())

    def configure(self, **kw):
        if 'state' in kw:
            self._state = kw.pop('state')
            self._entry.configure(state=self._state)
            if self._btn:
                self._btn.configure(state=self._state)
        super().configure(**kw)
