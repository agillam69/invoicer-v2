"""
smart_clipboard.py
==================
Reusable clipboard utilities for ttk.Treeview widgets.

Public API
----------
bind_treeview_clipboard(tree, root_widget)
    Attaches to any ttk.Treeview:
    - Right-click context menu: Copy Row(s), Copy Cell, Copy All, Select All
    - Ctrl+C        copy selected rows as tab-separated text
    - Ctrl+A        select all rows
    - Ctrl+Shift+C  copy ALL rows (ignoring selection)

parse_clipboard_table(text, expected_cols=None)
    Parse tab- or comma-separated clipboard text into a list of dicts.

    Delimiter: auto-detected (tab wins if any tab present in first line).

    Header detection:
    - If first row values look like column names (no spaces, no @, not
      pure digits) it is treated as a header regardless of whether the
      values match expected_cols.
    - If expected_cols is supplied and the first row matches exactly,
      those column names are used as dict keys.
    - If no recognisable header exists and expected_cols is given, rows
      are mapped positionally to expected_cols.
    - If no recognisable header and no expected_cols, positional integer
      keys ('0', '1', ...) are used so all rows are treated as data.

    Name splitting (automatic, via _normalise_records):
    - If the result has no first_name/last_name keys but has a column
      whose name is in _FULL_NAME_COLS ('name', 'full_name', 'fullname',
      'student_name', 'participant', 'attendee', ...), that column is
      split on the first space into first_name / last_name.
    - 'Last, First' comma format is also handled (inverted correctly).
    - Fallback: if the first column value contains a space and doesn't
      look like an email or number, it is treated as a full name.

clipboard_text(widget)
    Returns clipboard contents as a string, or '' on TclError.

BulkEditDialog(parent, fields, options=None)
    Modal dialog for applying one field+value change to multiple rows.
    fields   — list of (label, key) pairs the user can choose from.
    options  — dict mapping key -> list-of-values for dropdown fields;
               keys absent from options get a free-text Entry.
    .result  — None if cancelled, else {'field': key, 'value': new_value}.
"""

import tkinter as tk
from tkinter import ttk
import io
import csv


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _tree_rows_as_text(tree: ttk.Treeview, iids=None) -> str:
    """Return treeview rows as tab-separated text (header + data)."""
    cols = tree['columns']
    header = '\t'.join(tree.heading(c)['text'] for c in cols)
    if iids is None:
        iids = tree.get_children()
    lines = [header]
    for iid in iids:
        vals = tree.item(iid, 'values')
        lines.append('\t'.join(str(v) for v in vals))
    return '\n'.join(lines)


def _copy_to_clipboard(widget: tk.Widget, text: str):
    widget.clipboard_clear()
    widget.clipboard_append(text)


def _cell_value(tree: ttk.Treeview, iid: str, x: int) -> str:
    """Return the value of the cell column at pixel x for the given row."""
    cols = tree['columns']
    offset = 0
    for c in cols:
        w = tree.column(c, option='width')
        if x <= offset + w:
            vals = tree.item(iid, 'values')
            idx = list(cols).index(c)
            return str(vals[idx]) if idx < len(vals) else ''
        offset += w
    return ''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def bind_treeview_clipboard(tree: ttk.Treeview, root: tk.Widget,
                            extra_menu_fn=None):
    """
    Attach clipboard bindings and a right-click context menu to *tree*.
    *root* is any widget in the same Tk instance (used for clipboard ops).

    extra_menu_fn(event, menu) — optional callable invoked before the menu
        is shown.  It should call menu.add_command / add_separator etc. to
        inject additional items.  The clicked column name is available via
        tree._last_right_col and the clicked iid via tree._last_right_iid.
    """
    menu = tk.Menu(tree, tearoff=0)

    def _copy_selected(event=None):
        sel = tree.selection()
        if not sel:
            return
        text = _tree_rows_as_text(tree, sel)
        _copy_to_clipboard(root, text)

    def _copy_all(event=None):
        text = _tree_rows_as_text(tree)
        _copy_to_clipboard(root, text)

    def _select_all(event=None):
        for iid in tree.get_children():
            tree.selection_add(iid)

    def _copy_cell(event=None):
        sel = tree.selection()
        if not sel:
            return
        x = getattr(tree, '_last_right_x', 0)
        text = _cell_value(tree, sel[0], x)
        _copy_to_clipboard(root, text)

    def _show_menu(event):
        tree._last_right_x = event.x
        # Identify clicked row and column
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set(iid)
        tree._last_right_iid = iid or ''
        col_tk = tree.identify_column(event.x)
        try:
            col_idx = int(col_tk.lstrip('#')) - 1
            cols = tree['columns']
            tree._last_right_col = cols[col_idx] if 0 <= col_idx < len(cols) else ''
        except (ValueError, AttributeError):
            tree._last_right_col = ''

        # Rebuild dynamic portion of menu
        for idx in range(menu.index('end') + 1):
            try:
                menu.delete(0)
            except Exception:
                break

        # Extra (caller-injected) items at top
        if extra_menu_fn and iid:
            extra_menu_fn(event, menu)
            menu.add_separator()

        sel = tree.selection()
        menu.add_command(label='Copy Row(s)',   command=_copy_selected,
                         state='normal' if sel else 'disabled')
        menu.add_command(label='Copy Cell',     command=_copy_cell,
                         state='normal' if sel else 'disabled')
        menu.add_command(label='Copy All Rows', command=_copy_all)
        menu.add_separator()
        menu.add_command(label='Select All',    command=_select_all)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree.bind('<Button-3>',        _show_menu)
    tree.bind('<Control-c>',       lambda e: _copy_selected())
    tree.bind('<Control-C>',       lambda e: _copy_selected())
    tree.bind('<Control-A>',       lambda e: _select_all())
    tree.bind('<Control-a>',       lambda e: _select_all())
    tree.bind('<Control-Shift-c>', lambda e: _copy_all())
    tree.bind('<Control-Shift-C>', lambda e: _copy_all())


# ---------------------------------------------------------------------------
# Clipboard paste parser
# ---------------------------------------------------------------------------
def _split_name(full: str) -> tuple:
    """
    Split a combined "Firstname Lastname" string.
    Handles:
      - "John Smith"       -> ("John", "Smith")
      - "John"             -> ("John", "")
      - "Mary Jane Watson" -> ("Mary", "Jane Watson")   [first + rest]
      - "Smith, John"      -> ("John", "Smith")          [Last, First]
    """
    full = full.strip()
    if ',' in full:
        # "Last, First" format
        parts = [p.strip() for p in full.split(',', 1)]
        return (parts[1], parts[0])
    parts = full.split(None, 1)
    if len(parts) == 1:
        return (parts[0], '')
    return (parts[0], parts[1])


# Column names that indicate a combined full name
_FULL_NAME_COLS = {
    'name', 'full_name', 'fullname', 'student_name', 'student name',
    'participant', 'participant name', 'attendee',
}


def _normalise_records(records: list) -> list:
    """
    Post-process parsed records to handle combined name columns.

    If a record has no first_name/last_name keys but has a key whose
    name (lowercased) is in _FULL_NAME_COLS, split it and inject
    first_name / last_name.

    Also handles the common two-column paste where column 1 is
    "Firstname Lastname" and column 2 is "email" — detected by
    checking whether the first key's values contain spaces while
    first_name/last_name are absent.
    """
    if not records:
        return records

    # Check first record for a combined name column
    sample = records[0]
    keys_lower = {k.lower(): k for k in sample.keys()}

    has_first = 'first_name' in keys_lower
    has_last  = 'last_name'  in keys_lower

    if has_first and has_last:
        return records   # already split — nothing to do

    # Find which column is the combined name
    name_col = None
    for col_lower, col_orig in keys_lower.items():
        if col_lower in _FULL_NAME_COLS:
            name_col = col_orig
            break

    # Fallback: if no recognised name col, check whether the FIRST
    # column value (in the first record) contains a space and looks
    # like a name (not an email, not a date, not a number).
    if name_col is None:
        first_key = next(iter(sample))
        first_val = sample.get(first_key, '')
        if (
            ' ' in first_val
            and '@' not in first_val
            and not first_val[0].isdigit()
        ):
            name_col = first_key

    if name_col is None:
        return records   # can't determine — return as-is

    result = []
    for rec in records:
        combined = rec.pop(name_col, '')
        fn, ln = _split_name(combined)
        # Only inject if not already present
        new_rec = {}
        if 'first_name' not in rec:
            new_rec['first_name'] = fn
        if 'last_name' not in rec:
            new_rec['last_name'] = ln
        new_rec.update(rec)
        result.append(new_rec)
    return result


def parse_clipboard_table(text: str, expected_cols: list = None) -> list:
    """
    Parse tab- or comma-separated text into a list of dicts.

    Rules
    -----
    1. Auto-detect delimiter: tabs win if any line has a tab; else commas.
    2. If the first row matches (case-insensitive) the expected_cols list,
       treat it as a header row — use it for keys.
    3. If expected_cols is given but first row doesn't match, map data
       positionally to expected_cols.
    4. Blank rows are skipped.
    5. Combined "Firstname Lastname" columns are automatically split into
       first_name / last_name (see _normalise_records).
       Recognised column names: name, full_name, student_name, participant…
       Fallback: if the first column contains spaces and looks like a name.

    Returns list of dicts (may be empty).
    """
    text = text.strip()
    if not text:
        return []

    # Detect delimiter
    delim = '\t' if '\t' in text.split('\n')[0] else ','

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []

    # Decide header
    first = [c.strip().lower() for c in rows[0]]

    def _looks_like_header(cells: list) -> bool:
        """Return True if every cell looks like a column name (no @, no pure digits, no spaces)."""
        if not cells:
            return False
        return all(
            c and '@' not in c and not c.replace('.', '').replace('_', '').isdigit()
            and ' ' not in c
            for c in cells
        )

    if expected_cols:
        exp_lower = [c.lower() for c in expected_cols]
        if first == exp_lower or all(c in exp_lower for c in first):
            # First row exactly matches expected columns
            header = [c.strip() for c in rows[0]]
            data   = rows[1:]
        elif _looks_like_header(first):
            # First row looks like column names even if they don't match expected_cols
            # (e.g. "name,email,phone" vs full STUDENT_FIELDS)
            header = [c.strip() for c in rows[0]]
            data   = rows[1:]
        else:
            # No recognisable header — map positionally
            header = expected_cols
            data   = rows
    else:
        # Treat first row as header only if it looks like column names
        if _looks_like_header(first):
            header = [c.strip() for c in rows[0]]
            data   = rows[1:]
        else:
            # All rows are data; use positional integer keys
            header = [str(i) for i in range(len(rows[0]))]
            data   = rows

    result = []
    for row in data:
        if not any(c.strip() for c in row):
            continue
        record = {}
        for i, key in enumerate(header):
            record[key] = row[i].strip() if i < len(row) else ''
        result.append(record)

    return _normalise_records(result)


def clipboard_text(widget: tk.Widget) -> str:
    """Return clipboard content as a string, or '' on failure."""
    try:
        return widget.clipboard_get()
    except tk.TclError:
        return ''


# ---------------------------------------------------------------------------
# Bulk edit dialog
# ---------------------------------------------------------------------------
class BulkEditDialog(tk.Toplevel):
    """
    Pick a field and a new value; apply to all selected rows.

    Parameters
    ----------
    parent  : tk widget (parent window)
    fields  : list of (label, key) — the editable fields
    options : dict key -> [value, ...] for fields that should be a dropdown;
              keys not in options get a free-text Entry widget.
    count   : number of rows that will be affected (shown in the header).
    """

    def __init__(self, parent, fields: list, options: dict = None, count: int = 0):
        super().__init__(parent)
        self.title('Bulk Edit')
        self.resizable(False, False)
        self.grab_set()
        self.fields  = fields          # [(label, key), ...]
        self.options = options or {}
        self.count   = count
        self.result  = None            # {'field': key, 'value': val} or None
        self._build()
        self.wait_window(self)

    def _build(self):
        pad = {'padx': 10, 'pady': 4}

        ttk.Label(self,
                  text=f'Set one field on {self.count} selected row(s):',
                  font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=10, pady=(10, 4))

        # Field selector
        ttk.Label(self, text='Field:').grid(row=1, column=0, sticky='e', **pad)
        self._field_labels = [lbl for lbl, _ in self.fields]
        self._field_keys   = [key for _, key in self.fields]
        self._field_var = tk.StringVar(value=self._field_labels[0])
        field_cb = ttk.Combobox(self, textvariable=self._field_var,
                                values=self._field_labels, state='readonly', width=22)
        field_cb.grid(row=1, column=1, sticky='w', **pad)
        field_cb.bind('<<ComboboxSelected>>', self._on_field_change)

        # Value input — swapped dynamically
        ttk.Label(self, text='New value:').grid(row=2, column=0, sticky='e', **pad)
        self._value_frame = ttk.Frame(self)
        self._value_frame.grid(row=2, column=1, sticky='w', **pad)
        self._value_var = tk.StringVar()
        self._value_widget = None
        self._rebuild_value_widget(self._field_keys[0])

        # Buttons
        btn = ttk.Frame(self)
        btn.grid(row=3, column=0, columnspan=2, pady=(6, 10))
        ttk.Button(btn, text='Apply', command=self._apply).pack(side='left', padx=6)
        ttk.Button(btn, text='Cancel', command=self.destroy).pack(side='left')

    def _rebuild_value_widget(self, key: str):
        """Replace the value widget with a Combobox or Entry depending on key."""
        if self._value_widget:
            self._value_widget.destroy()
        opts = self.options.get(key)
        if opts:
            self._value_var.set(opts[0])
            self._value_widget = ttk.Combobox(
                self._value_frame, textvariable=self._value_var,
                values=opts, state='readonly', width=24)
        else:
            self._value_var.set('')
            self._value_widget = ttk.Entry(
                self._value_frame, textvariable=self._value_var, width=26)
        self._value_widget.pack()
        self._value_widget.focus_set()

    def _on_field_change(self, event=None):
        label = self._field_var.get()
        idx   = self._field_labels.index(label)
        key   = self._field_keys[idx]
        self._rebuild_value_widget(key)

    def _apply(self):
        label = self._field_var.get()
        idx   = self._field_labels.index(label)
        key   = self._field_keys[idx]
        value = self._value_var.get().strip()
        self.result = {'field': key, 'value': value}
        self.destroy()
