"""
ledger_tab.py
=============
Ledger tab — record money in / out (non-invoice transactions).
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from app_theme import configure_tags, LABEL_SUCCESS, LABEL_MUTED
from datetime import datetime, date, timedelta
from smart_clipboard import bind_treeview_clipboard, parse_clipboard_table, clipboard_text
from date_utils import DateEntry, fmt_display, storage_to_display, display_to_storage, parse_date
from app_log import get_logger, log_event, log_summary

_log = get_logger('ledger')

CATEGORIES_IN  = ['Invoice Payment', 'Grant', 'Refund', 'Other Income']
CATEGORIES_OUT = ['Supplies', 'Certification Fee', 'Equipment', 'Software',
                  'Travel', 'Training', 'Wages', 'Utilities', 'Other Expense']


class LedgerTab:
    def __init__(self, parent_notebook, ds, currency_fn):
        """
        parent_notebook : ttk.Notebook to add the tab into
        ds              : DataStore instance
        currency_fn     : callable() -> currency symbol string
        """
        self.ds = ds
        self.currency_fn = currency_fn
        self._editing_id = None

        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text='Ledger')
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        top = ttk.Frame(self.frame)
        top.pack(fill='x', padx=8, pady=4)

        # ---- Filter / search bar ----
        flt = ttk.LabelFrame(top, text='Filter')
        flt.pack(fill='x', pady=(0, 4))

        row0 = ttk.Frame(flt)
        row0.pack(fill='x', padx=6, pady=(4, 2))

        ttk.Label(row0, text='Search:').pack(side='left')
        self._search_var = tk.StringVar()
        ttk.Entry(row0, textvariable=self._search_var, width=20).pack(side='left', padx=(3, 8))
        self._search_var.trace_add('write', lambda *_: self._apply_filter())

        ttk.Label(row0, text='Type:').pack(side='left')
        self._flt_type_var = tk.StringVar(value='All')
        ttk.Combobox(row0, textvariable=self._flt_type_var,
                     values=['All', 'in', 'out'], state='readonly', width=6
                     ).pack(side='left', padx=(3, 8))
        self._flt_type_var.trace_add('write', lambda *_: self._apply_filter())

        ttk.Label(row0, text='Category:').pack(side='left')
        self._flt_cat_var = tk.StringVar(value='All')
        all_cats = ['All'] + CATEGORIES_IN + CATEGORIES_OUT
        self._flt_cat_cb = ttk.Combobox(row0, textvariable=self._flt_cat_var,
                                         values=all_cats, state='readonly', width=18)
        self._flt_cat_cb.pack(side='left', padx=(3, 8))
        self._flt_cat_var.trace_add('write', lambda *_: self._apply_filter())

        ttk.Button(row0, text='Clear Filters', command=self._clear_filters
                   ).pack(side='right', padx=3)

        row1 = ttk.Frame(flt)
        row1.pack(fill='x', padx=6, pady=(0, 4))

        ttk.Label(row1, text='From:').pack(side='left')
        self._flt_from_var = tk.StringVar()
        DateEntry(row1, textvariable=self._flt_from_var, width=11
                  ).pack(side='left', padx=(3, 8))
        self._flt_from_var.trace_add('write', lambda *_: self._apply_filter())

        ttk.Label(row1, text='To:').pack(side='left')
        self._flt_to_var = tk.StringVar()
        DateEntry(row1, textvariable=self._flt_to_var, width=11
                  ).pack(side='left', padx=(3, 8))
        self._flt_to_var.trace_add('write', lambda *_: self._apply_filter())

        for label, fn in [
            ('This Week',  self._range_this_week),
            ('This Month', self._range_this_month),
            ('Last Month', self._range_last_month),
            ('This Year',  self._range_this_year),
            ('All',        self._range_all),
        ]:
            ttk.Button(row1, text=label, command=fn).pack(side='left', padx=2)

        # ---- Entry form ----
        form = ttk.LabelFrame(top, text='Entry')
        form.pack(fill='x')

        pad = {'padx': 5, 'pady': 3}

        ttk.Label(form, text='Date:').grid(row=0, column=0, sticky='e', **pad)
        self._date_var = tk.StringVar(value=fmt_display(datetime.now().date()))
        DateEntry(form, textvariable=self._date_var, width=12).grid(row=0, column=1, sticky='w', **pad)

        ttk.Label(form, text='Type:').grid(row=0, column=2, sticky='e', **pad)
        self._type_var = tk.StringVar(value='in')
        type_cb = ttk.Combobox(form, textvariable=self._type_var,
                               values=['in', 'out'], state='readonly', width=6)
        type_cb.grid(row=0, column=3, sticky='w', **pad)
        type_cb.bind('<<ComboboxSelected>>', self._on_type_change)

        ttk.Label(form, text='Category:').grid(row=0, column=4, sticky='e', **pad)
        self._cat_var = tk.StringVar()
        self._cat_cb = ttk.Combobox(form, textvariable=self._cat_var, width=20, state='readonly')
        self._cat_cb.grid(row=0, column=5, sticky='w', **pad)
        self._on_type_change()

        ttk.Label(form, text='Amount:').grid(row=1, column=0, sticky='e', **pad)
        self._amount_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._amount_var, width=12).grid(row=1, column=1, sticky='w', **pad)

        ttk.Label(form, text='Description:').grid(row=1, column=2, sticky='e', **pad)
        self._desc_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._desc_var, width=28).grid(row=1, column=3, columnspan=2, sticky='w', **pad)

        ttk.Label(form, text='Reference:').grid(row=2, column=0, sticky='e', **pad)
        self._ref_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._ref_var, width=18).grid(row=2, column=1, sticky='w', **pad)

        ttk.Label(form, text='Notes:').grid(row=2, column=2, sticky='e', **pad)
        self._notes_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._notes_var, width=40).grid(row=2, column=3, columnspan=3, sticky='w', **pad)

        btn_row = ttk.Frame(form)
        btn_row.grid(row=3, column=0, columnspan=6, sticky='w', padx=5, pady=4)
        self._add_btn = ttk.Button(btn_row, text='Add Entry', command=self._add_entry)
        self._add_btn.pack(side='left', padx=3)
        ttk.Button(btn_row, text='Edit Selected', command=self._edit_selected).pack(side='left', padx=3)
        ttk.Button(btn_row, text='Clear', command=self._clear_form).pack(side='left', padx=3)
        ttk.Button(btn_row, text='Delete Selected', command=self._delete_entry).pack(side='left', padx=3)

        # ---- Summary bar ----
        self._summary_var = tk.StringVar(value='')
        ttk.Label(top, textvariable=self._summary_var, foreground=LABEL_SUCCESS,
                  font=('TkDefaultFont', 9, 'bold')).pack(anchor='e', padx=8)

        # ---- Tree ----
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=4)

        cols = ('date', 'type', 'category', 'description', 'amount', 'reference', 'notes')
        self._tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=16)
        widths = {'date': 90, 'type': 50, 'category': 140, 'description': 200,
                  'amount': 90, 'reference': 110, 'notes': 200}
        self._sort_col   = 'date'
        self._sort_asc   = True
        for c in cols:
            self._tree.heading(c, text=c.title(),
                               command=lambda _c=c: self._sort_by(_c))
            self._tree.column(c, width=widths[c], anchor='w')
        self._tree.column('amount', anchor='e')
        self._all_rows_cache: list = []

        sb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        configure_tags(self._tree, ['in', 'out'])
        self._tree.bind('<Double-1>', self._on_double_click)

        bottom = ttk.Frame(self.frame)
        bottom.pack(fill='x', padx=8, pady=2)
        ttk.Button(bottom, text='Paste from Clipboard', command=self._paste_from_clipboard).pack(side='left', padx=3)
        ttk.Button(bottom, text='Import from CSV…',     command=self._import_csv).pack(side='left', padx=3)
        ttk.Button(bottom, text='Export to CSV…',       command=self._export_csv).pack(side='left', padx=3)
        ttk.Button(bottom, text='Refresh',               command=self.refresh).pack(side='right', padx=3)
        bind_treeview_clipboard(self._tree, self.frame)

    # ------------------------------------------------------------------
    # Quick date-range helpers
    # ------------------------------------------------------------------
    def _set_range(self, from_d, to_d):
        self._flt_from_var.set(fmt_display(from_d) if from_d else '')
        self._flt_to_var.set(fmt_display(to_d)   if to_d   else '')

    def _range_this_week(self):
        today = date.today()
        self._set_range(today - timedelta(days=today.weekday()), today)

    def _range_this_month(self):
        today = date.today()
        self._set_range(today.replace(day=1), today)

    def _range_last_month(self):
        today = date.today()
        first_this = today.replace(day=1)
        last_prev  = first_this - timedelta(days=1)
        self._set_range(last_prev.replace(day=1), last_prev)

    def _range_this_year(self):
        today = date.today()
        self._set_range(today.replace(month=1, day=1), today)

    def _range_all(self):
        self._set_range(None, None)

    def _clear_filters(self):
        self._search_var.set('')
        self._flt_type_var.set('All')
        self._flt_cat_var.set('All')
        self._range_all()

    # ------------------------------------------------------------------
    # Sort
    # ------------------------------------------------------------------
    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._update_sort_indicators()
        self._apply_filter()

    def _update_sort_indicators(self):
        cols = ('date', 'type', 'category', 'description', 'amount', 'reference', 'notes')
        for c in cols:
            label = c.title()
            if c == self._sort_col:
                label += ' ▲' if self._sort_asc else ' ▼'
            self._tree.heading(c, text=label)

    # ------------------------------------------------------------------
    # Filter + display
    # ------------------------------------------------------------------
    def _apply_filter(self):
        search   = self._search_var.get().strip().lower()
        ftype    = self._flt_type_var.get()
        fcat     = self._flt_cat_var.get()
        from_str = self._flt_from_var.get().strip()
        to_str   = self._flt_to_var.get().strip()
        from_d   = parse_date(from_str) if from_str else None
        to_d     = parse_date(to_str)   if to_str   else None

        visible = []
        for r in self._all_rows_cache:
            if ftype != 'All' and r.get('type') != ftype:
                continue
            if fcat != 'All' and r.get('category') != fcat:
                continue
            row_date = parse_date(r.get('date', ''))
            if from_d and row_date and row_date < from_d:
                continue
            if to_d and row_date and row_date > to_d:
                continue
            if search:
                haystack = ' '.join(str(v) for v in r.values()).lower()
                if search not in haystack:
                    continue
            visible.append(r)

        # Sort
        col = self._sort_col
        reverse = not self._sort_asc
        def _key(r):
            v = r.get(col, '')
            if col == 'amount':
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return 0.0
            if col == 'date':
                d = parse_date(str(v))
                return d.isoformat() if d else ''
            return str(v).lower()
        visible.sort(key=_key, reverse=reverse)

        self._render_rows(visible)

    def _render_rows(self, rows):
        for item in self._tree.get_children():
            self._tree.delete(item)
        sym = self.currency_fn()
        total_in = total_out = 0.0
        for row in rows:
            try:
                amt = float(row.get('amount', 0))
            except (ValueError, TypeError):
                amt = 0.0
            etype = row.get('type', '')
            if etype == 'in':
                total_in  += amt
                display_amt = f'+{sym}{amt:.2f}'
            else:
                total_out += amt
                display_amt = f'-{sym}{amt:.2f}'
            self._tree.insert('', 'end',
                tags=(row.get('id', ''),),
                values=(
                    storage_to_display(row.get('date', '')),
                    etype,
                    row.get('category', ''),
                    row.get('description', ''),
                    display_amt,
                    row.get('reference', ''),
                    row.get('notes', ''),
                ))
        net  = total_in - total_out
        sign = '+' if net >= 0 else ''
        total_rows = len(self._all_rows_cache)
        shown      = len(rows)
        count_note = f'  ({shown} of {total_rows} rows)' if shown != total_rows else f'  ({total_rows} rows)'
        summary = (f'In: {sym}{total_in:.2f}   Out: {sym}{total_out:.2f}   '
                   f'Net: {sign}{sym}{net:.2f}{count_note}')
        self._summary_var.set(summary)

    # ------------------------------------------------------------------
    def _on_type_change(self, event=None):
        if self._type_var.get() == 'in':
            self._cat_cb['values'] = CATEGORIES_IN
        else:
            self._cat_cb['values'] = CATEGORIES_OUT
        self._cat_var.set('')

    def _clear_form(self):
        self._date_var.set(fmt_display(datetime.now().date()))
        self._type_var.set('in')
        self._on_type_change()
        self._amount_var.set('')
        self._desc_var.set('')
        self._ref_var.set('')
        self._notes_var.set('')
        self._editing_id = None
        self._add_btn.config(text='Add Entry')

    def _add_entry(self):
        date  = self._date_var.get().strip()
        etype = self._type_var.get().strip()
        cat   = self._cat_var.get().strip()
        desc  = self._desc_var.get().strip()
        ref   = self._ref_var.get().strip()
        notes = self._notes_var.get().strip()

        if not date:
            messagebox.showwarning('Missing date', 'Enter a date.', parent=self.frame)
            return
        if not desc:
            messagebox.showwarning('Missing description', 'Enter a description.', parent=self.frame)
            return
        try:
            amount = float(self._amount_var.get().replace(',', ''))
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning('Invalid amount', 'Enter a positive number for amount.', parent=self.frame)
            return

        date_storage = display_to_storage(date) or date
        if self._editing_id:
            self.ds.update_ledger(self._editing_id, {
                'date': date_storage, 'type': etype, 'category': cat,
                'description': desc, 'amount': f'{amount:.2f}',
                'reference': ref, 'notes': notes,
            })
            log_event('ledger', 'updated', f'id={self._editing_id} {etype} {cat} ${amount:.2f} {desc}')
        else:
            self.ds.append_ledger({
                'date': date_storage, 'type': etype, 'category': cat,
                'description': desc, 'amount': f'{amount:.2f}',
                'reference': ref, 'notes': notes,
            })
            log_event('ledger', 'created', f'{etype} {cat} ${amount:.2f} {desc}')

        self._clear_form()
        self.refresh()

    def _delete_entry(self):
        sel = self._tree.selection()
        if not sel:
            return
        tags = self._tree.item(sel[0], 'tags')
        entry_id = tags[0] if tags else None
        if not entry_id:
            return
        if not messagebox.askyesno('Confirm', 'Delete this entry?', parent=self.frame):
            return
        self.ds.delete_ledger(entry_id)
        log_event('ledger', 'deleted', f'id={entry_id}')
        self._clear_form()
        self.refresh()

    def _edit_selected(self):
        """Load the currently selected tree row into the form for editing."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo('Select entry', 'Select a ledger entry to edit.', parent=self.frame)
            return
        self._load_item(sel[0])

    def _load_item(self, item):
        """Populate the form from a treeview item."""
        vals = self._tree.item(item, 'values')
        tags = self._tree.item(item, 'tags')
        if not tags:
            return
        self._tree.selection_set(item)
        self._editing_id = tags[0]
        # vals: date, type, category, description, amount, reference, notes
        self._date_var.set(storage_to_display(vals[0]) if vals[0] else '')
        self._type_var.set(vals[1])
        self._on_type_change()
        self._cat_var.set(vals[2])
        self._desc_var.set(vals[3])
        sym = self.currency_fn()
        raw_amt = str(vals[4]).replace(sym, '').strip().lstrip('+-').strip()
        self._amount_var.set(raw_amt)
        self._ref_var.set(vals[5])
        self._notes_var.set(vals[6])
        self._add_btn.config(text='Update Entry')

    def _on_double_click(self, event):
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._load_item(item)

    def _paste_from_clipboard(self):
        """Parse tab/CSV data from clipboard and import as ledger entries."""
        text = clipboard_text(self.frame)
        if not text.strip():
            messagebox.showinfo('Nothing to paste',
                'Copy rows of ledger data to the clipboard first (date, type, category, '
                'description, amount, reference, notes).', parent=self.frame)
            return
        cols = ['date', 'type', 'category', 'description', 'amount', 'reference', 'notes']
        rows = parse_clipboard_table(text, expected_cols=cols)
        if not rows:
            messagebox.showwarning('Could not parse',
                'No valid rows found. Ensure data has at least date, type, description and amount.',
                parent=self.frame)
            return
        count = 0
        skipped = 0
        for row in rows:
            date  = row.get('date', '').strip()
            etype = row.get('type', 'out').strip().lower()
            desc  = row.get('description', '').strip()
            try:
                amt = float(str(row.get('amount', '0')).replace(',', '').replace('$', '').strip())
                if amt <= 0:
                    raise ValueError
            except ValueError:
                skipped += 1
                continue
            if not date or not desc:
                skipped += 1
                continue
            if etype not in ('in', 'out'):
                etype = 'out'
            self.ds.append_ledger({
                'date':        date,
                'type':        etype,
                'category':    row.get('category', '').strip(),
                'description': desc,
                'amount':      f'{abs(amt):.2f}',
                'reference':   row.get('reference', '').strip(),
                'notes':       row.get('notes', '').strip(),
            })
            count += 1
        self.refresh()
        msg = f'{count} entries imported.'
        if skipped:
            msg += f'  {skipped} skipped (missing/invalid data).'
        messagebox.showinfo('Paste complete', msg, parent=self.frame)

    def _import_csv(self):
        """Import ledger entries from a CSV file."""
        path = filedialog.askopenfilename(
            title='Import Ledger CSV',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            parent=self.frame)
        if not path:
            return
        try:
            import csv as _csv
            with open(path, newline='', encoding='utf-8-sig') as f:
                text = f.read()
            self.frame.clipboard_clear()
            self.frame.clipboard_append(text)
            self._paste_from_clipboard()
        except Exception as e:
            _log.error('Import CSV failed: %s', e, exc_info=True)
            messagebox.showerror('Import failed', str(e), parent=self.frame)

    def _export_csv(self):
        """Export all ledger entries to a CSV file."""
        path = filedialog.asksaveasfilename(
            title='Export Ledger',
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            parent=self.frame)
        if not path:
            return
        try:
            import csv as _csv
            rows = self.ds.read_ledger()
            with open(path, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    w = _csv.DictWriter(f, fieldnames=rows[0].keys())
                    w.writeheader()
                    w.writerows(rows)
            log_summary('ledger_export_csv', {'rows': len(rows), 'path': str(path)})
            messagebox.showinfo('Exported',
                f'{len(rows)} entries exported to:\n{path}', parent=self.frame)
        except Exception as e:
            _log.error('Export CSV failed: %s', e, exc_info=True)
            messagebox.showerror('Export failed', str(e), parent=self.frame)

    def refresh(self):
        try:
            self._all_rows_cache = self.ds.read_ledger()
        except Exception as e:
            _log.error('Ledger refresh failed: %s', e, exc_info=True)
            self._all_rows_cache = []
        self._apply_filter()
