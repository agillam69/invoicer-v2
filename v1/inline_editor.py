"""
inline_editor.py
================
Reusable inline cell editor for ttk.Treeview widgets.

Usage
-----
    from inline_editor import InlineCellEditor

    editor = InlineCellEditor(
        tree         = self._my_tree,
        col_names    = ('id', 'name', 'date', 'status', ...),  # in display order
        col_types    = {                                         # per-column widget type
            'date':   'date',
            'status': ('combo', ['active', 'inactive']),
            'id':     'readonly',                               # never editable
        },
        on_commit    = self._save_row,   # called with (iid, col_name, new_value)
        id_col       = 'id',             # column whose value is the record id
    )

    # bind to the tree:
    tree.bind('<Double-1>', editor.on_double_click)
    tree.bind('<Button-1>', lambda e: editor.commit())
    tree.bind('<Escape>',   lambda e: editor.cancel())

Column type values
------------------
    'text'            plain Entry (default)
    'readonly'        do not open editor
    'date'            DateEntry with calendar picker
    ('combo', [...])  Combobox with given values
    ('combo_fn', fn)  Combobox whose values come from fn()
"""

import tkinter as tk
from tkinter import ttk
from date_utils import DateEntry, display_to_storage, storage_to_display, parse_date, fmt_display


class InlineCellEditor:
    """Floats an appropriate widget over a treeview cell on double-click."""

    def __init__(self, tree, col_names, col_types=None,
                 on_commit=None, id_col=None):
        """
        tree       : ttk.Treeview
        col_names  : sequence of column field names in display order
        col_types  : dict  field -> type spec (see module docstring)
        on_commit  : callable(iid, col_name, display_value, storage_value)
        id_col     : name of the ID column (skipped for editing)
        """
        self._tree      = tree
        self._col_names = list(col_names)
        self._types     = col_types or {}
        self._on_commit = on_commit
        self._id_col    = id_col

        self._widget    = None   # currently open widget
        self._var       = None
        self._iid       = None
        self._col_name  = None
        self._col_idx   = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def on_double_click(self, event):
        self.commit()
        region = self._tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_tk  = self._tree.identify_column(event.x)
        iid     = self._tree.identify_row(event.y)
        if not iid:
            return
        col_idx  = int(col_tk.lstrip('#')) - 1
        col_name = self._col_names[col_idx] if col_idx < len(self._col_names) else None
        if not col_name:
            return
        ctype = self._types.get(col_name, 'text')
        if ctype == 'readonly':
            return
        self._start_edit(iid, col_idx, col_name, ctype)

    def commit(self, event=None):
        if self._widget is None:
            return
        raw = self._var.get().strip()
        ctype = self._types.get(self._col_name, 'text')

        # Normalise dates to display format for the tree; get storage value
        if ctype == 'date':
            d = parse_date(raw)
            display_val = fmt_display(d) if d else raw
            storage_val = d.strftime('%Y-%m-%d') if d else ''
        else:
            display_val = raw
            storage_val = raw

        vals = list(self._tree.item(self._iid, 'values'))
        vals[self._col_idx] = display_val
        self._tree.item(self._iid, values=tuple(vals))

        if self._on_commit:
            try:
                self._on_commit(self._iid, self._col_name, display_val, storage_val)
            except Exception:
                pass

        self._widget.destroy()
        self._widget = None

    def cancel(self, event=None):
        if self._widget:
            self._widget.destroy()
            self._widget = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _start_edit(self, iid, col_idx, col_name, ctype):
        # Use the tree's internal column id (e.g. '#1', '#2', …)
        tree_col_ids = self._tree['columns']
        if col_idx >= len(tree_col_ids):
            return
        tree_col_id = tree_col_ids[col_idx]
        bbox = self._tree.bbox(iid, tree_col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        current = self._tree.item(iid, 'values')[col_idx]

        self._iid      = iid
        self._col_idx  = col_idx
        self._col_name = col_name
        self._var      = tk.StringVar(value=str(current))

        if ctype == 'date':
            widget = DateEntry(self._tree, textvariable=self._var, width=max(10, w // 8))
            widget.place(x=x, y=y, width=w + 28, height=h + 2)
            widget._entry.focus_set()
            widget._entry.bind('<Return>', lambda e: self.commit())
            widget._entry.bind('<Escape>', lambda e: self.cancel())
            widget._entry.bind('<Tab>',    lambda e: self.commit())

        elif isinstance(ctype, (list, tuple)) and ctype[0] == 'combo':
            values = ctype[1]
            widget = ttk.Combobox(self._tree, textvariable=self._var,
                                  values=values, state='readonly', width=max(10, w // 8))
            widget.place(x=x, y=y, width=w, height=h + 2)
            widget.focus_set()
            widget.bind('<<ComboboxSelected>>', lambda e: self.commit())
            widget.bind('<Escape>', lambda e: self.cancel())

        elif isinstance(ctype, (list, tuple)) and ctype[0] == 'combo_fn':
            values = ctype[1]()
            widget = ttk.Combobox(self._tree, textvariable=self._var,
                                  values=values, state='readonly', width=max(10, w // 8))
            widget.place(x=x, y=y, width=w, height=h + 2)
            widget.focus_set()
            widget.bind('<<ComboboxSelected>>', lambda e: self.commit())
            widget.bind('<Escape>', lambda e: self.cancel())

        else:
            widget = ttk.Entry(self._tree, textvariable=self._var,
                               width=max(10, w // 8))
            widget.place(x=x, y=y, width=w, height=h + 2)
            widget.focus_set()
            widget.select_range(0, 'end')
            widget.bind('<Return>', lambda e: self.commit())
            widget.bind('<Tab>',    lambda e: self.commit())
            widget.bind('<Escape>', lambda e: self.cancel())

        self._widget = widget
