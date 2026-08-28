"""
report_preview.py
=================
ReportPreviewDialog — on-screen edit before PDF export.

Usage
-----
    from report_preview import ReportPreviewDialog

    dlg = ReportPreviewDialog(
        parent       = self.frame,
        title        = 'Ledger Report',
        columns      = ['Date', 'Type', 'Description', 'Amount'],
        rows         = [[...], ...],           # list of lists of str
        summary_lines= ['In: $500   Out: $200'],
        settings     = settings_dict,          # for colours/wording defaults
    )
    # dlg is modal; no return value needed — it handles its own PDF export.

What the dialog provides
------------------------
- Editable report title (pre-filled).
- Date-range label (free text, e.g. "Jan–Jun 2025").
- Free-text Notes field (appended to PDF below the table).
- Treeview of all rows with **double-click inline cell editing** —
  edits are for print only, not persisted to CSV.
- "Export PDF…" button: asks for save path, then calls build_report_pdf.
- "Close" button.
"""

import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from app_log import get_logger

_log = get_logger('report_preview')


class ReportPreviewDialog(tk.Toplevel):
    """
    Modal preview window:
    • Edit title / period / notes at the top
    • Double-click any cell to edit it (print-only)
    • Export PDF button
    """

    def __init__(self, parent, title: str, columns: list, rows: list,
                 summary_lines: list = None, settings: dict = None):
        super().__init__(parent)
        self.title(f'Preview — {title}')
        self.resizable(True, True)
        self.grab_set()
        self.minsize(900, 560)

        self._report_title   = title
        self._columns        = columns
        self._rows           = [list(r) for r in rows]   # mutable copy
        self._summary_lines  = summary_lines or []
        self._settings       = settings or {}
        self._edit_entry     = None   # in-place entry widget
        self._edit_iid       = None
        self._edit_col_idx   = None

        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        # ---- Header controls ----
        top = ttk.Frame(self, padding=8)
        top.pack(fill='x')

        pad = {'padx': 6, 'pady': 3}

        ttk.Label(top, text='Report title:').grid(row=0, column=0, sticky='e', **pad)
        self._title_var = tk.StringVar(value=self._report_title)
        ttk.Entry(top, textvariable=self._title_var, width=50).grid(row=0, column=1, sticky='w', **pad)

        ttk.Label(top, text='Period / date range:').grid(row=1, column=0, sticky='e', **pad)
        self._period_var = tk.StringVar(value=datetime.now().strftime('%B %Y'))
        ttk.Entry(top, textvariable=self._period_var, width=30).grid(row=1, column=1, sticky='w', **pad)

        ttk.Label(top, text='Notes (appear in PDF):').grid(row=2, column=0, sticky='ne', **pad)
        self._notes_text = tk.Text(top, width=60, height=3, wrap='word')
        self._notes_text.grid(row=2, column=1, sticky='w', **pad)

        # Summary lines preview
        if self._summary_lines:
            ttk.Label(top, text='Summary:').grid(row=3, column=0, sticky='ne', **pad)
            summary_lbl = ttk.Label(top,
                text='\n'.join(self._summary_lines),
                font=('Courier', 9), foreground='#1a5276')
            summary_lbl.grid(row=3, column=1, sticky='w', **pad)

        ttk.Separator(self, orient='horizontal').pack(fill='x')

        # ---- Treeview ----
        hint = ttk.Label(self,
            text='Double-click a cell to edit (edits are for print only, not saved to CSV)',
            foreground='grey', font=('TkDefaultFont', 8))
        hint.pack(anchor='w', padx=10, pady=(4, 0))

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=4)

        cols = tuple(f'c{i}' for i in range(len(self._columns)))
        self._tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=20)

        for i, (cid, label) in enumerate(zip(cols, self._columns)):
            self._tree.heading(cid, text=label)
            # auto width: wider for early columns, narrower for later ones
            w = max(70, min(200, 800 // max(len(self._columns), 1)))
            self._tree.column(cid, width=w, anchor='w')

        sb  = ttk.Scrollbar(tree_frame, orient='vertical',   command=self._tree.yview)
        sbx = ttk.Scrollbar(tree_frame, orient='horizontal',  command=self._tree.xview)
        self._tree.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
        self._tree.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        sbx.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree.bind('<Double-1>', self._on_double_click)
        self._tree.bind('<Button-1>',  self._commit_edit)
        self._tree.bind('<Escape>',    self._cancel_edit)

        self._populate_tree()

        # ---- Row count ----
        self._count_var = tk.StringVar(value=f'{len(self._rows)} row(s)')
        ttk.Label(self, textvariable=self._count_var, foreground='#555').pack(anchor='e', padx=10)

        # ---- Buttons ----
        ttk.Separator(self, orient='horizontal').pack(fill='x')
        btn = ttk.Frame(self, padding=8)
        btn.pack(fill='x')
        ttk.Button(btn, text='Export PDF…',  command=self._export_pdf).pack(side='left', padx=6)
        ttk.Button(btn, text='Export CSV…',  command=self._export_csv).pack(side='left', padx=2)
        ttk.Button(btn, text='Reset edits',  command=self._reset_edits).pack(side='left', padx=2)
        ttk.Button(btn, text='Close',        command=self.destroy).pack(side='right', padx=6)

    # ------------------------------------------------------------------
    def _populate_tree(self):
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        for row in self._rows:
            self._tree.insert('', 'end', values=tuple(row))

    # ------------------------------------------------------------------
    # Inline cell editing
    # ------------------------------------------------------------------
    def _on_double_click(self, event):
        self._commit_edit()
        region = self._tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id  = self._tree.identify_column(event.x)
        iid     = self._tree.identify_row(event.y)
        if not iid:
            return
        col_idx = int(col_id.lstrip('#')) - 1
        self._start_edit(iid, col_idx)

    def _start_edit(self, iid, col_idx):
        col_id = f'c{col_idx}'
        bbox   = self._tree.bbox(iid, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = self._tree.item(iid, 'values')[col_idx]

        var = tk.StringVar(value=current)
        entry = ttk.Entry(self._tree, textvariable=var)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, 'end')

        self._edit_entry   = entry
        self._edit_var     = var
        self._edit_iid     = iid
        self._edit_col_idx = col_idx

        entry.bind('<Return>',  lambda e: self._commit_edit())
        entry.bind('<Tab>',     lambda e: self._commit_edit())
        entry.bind('<Escape>',  lambda e: self._cancel_edit())

    def _commit_edit(self, event=None):
        if self._edit_entry is None:
            return
        new_val  = self._edit_var.get()
        iid      = self._edit_iid
        col_idx  = self._edit_col_idx

        vals     = list(self._tree.item(iid, 'values'))
        vals[col_idx] = new_val
        self._tree.item(iid, values=tuple(vals))

        # Update in-memory rows list
        row_idx = self._tree.get_children().index(iid)
        self._rows[row_idx][col_idx] = new_val

        self._edit_entry.destroy()
        self._edit_entry = None

    def _cancel_edit(self, event=None):
        if self._edit_entry:
            self._edit_entry.destroy()
            self._edit_entry = None

    def _reset_edits(self):
        self._populate_tree()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_csv(self):
        self._commit_edit()
        title = self._title_var.get().strip() or self._report_title
        default_name = title.replace(' ', '_').replace('/', '-') + '.csv'
        path = filedialog.asksaveasfilename(
            title='Save Report CSV',
            initialfile=default_name,
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('All files', '*.*')],
            parent=self)
        if not path:
            return
        rows = [list(self._tree.item(iid, 'values'))
                for iid in self._tree.get_children()]
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self._columns)
                writer.writerows(rows)
                if self._summary_lines:
                    writer.writerow([])
                    for line in self._summary_lines:
                        writer.writerow([line])
            _log.info('Report CSV exported: %s', path)
            messagebox.showinfo('CSV saved', f'Report saved to:\n{path}', parent=self)
        except Exception as e:
            _log.error('Report CSV export failed: %s', e, exc_info=True)
            messagebox.showerror('CSV error', str(e), parent=self)

    def _export_pdf(self):
        self._commit_edit()
        title  = self._title_var.get().strip() or self._report_title
        period = self._period_var.get().strip()
        notes  = self._notes_text.get('1.0', 'end').strip()

        # Collect current rows from treeview (may have been edited)
        rows = [list(self._tree.item(iid, 'values'))
                for iid in self._tree.get_children()]

        s   = self._settings
        org = (s.get('report_org_override') or s.get('business_name', '')).strip()

        summary = list(self._summary_lines)
        if period:
            summary.insert(0, f'Period: {period}')

        default_name = (title.replace(' ', '_').replace('/', '-') + '.pdf')
        path = filedialog.asksaveasfilename(
            title='Save Report PDF',
            initialfile=default_name,
            defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf'), ('All files', '*.*')],
            parent=self)
        if not path:
            return

        try:
            from report_pdf import build_report_pdf
            build_report_pdf(
                path=path,
                title=title,
                columns=self._columns,
                rows=rows,
                summary_lines=summary if summary else None,
                notes=notes,
                prepared_by=s.get('report_prepared_by', ''),
                footer=s.get('report_footer', ''),
                org=org,
                header_colour=s.get('report_header_colour', '#2C3E50'),
                accent_colour=s.get('report_accent_colour',  '#2980B9'),
                stripe_colour=s.get('report_stripe_colour',  '#EBF5FB'),
            )
            messagebox.showinfo('PDF saved',
                f'Report saved to:\n{path}', parent=self)
            # Try to open it
            import os, subprocess, sys
            try:
                if sys.platform == 'win32':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', path])
                else:
                    subprocess.Popen(['xdg-open', path])
            except Exception as open_err:
                _log.warning('Could not auto-open PDF: %s', open_err)
        except Exception as e:
            _log.error('Report PDF export failed: %s', e, exc_info=True)
            messagebox.showerror('PDF error', str(e), parent=self)
