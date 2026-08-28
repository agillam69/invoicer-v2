"""
reports_tab.py
==============
Reports & Audit tab — business summary, invoice ageing, ledger,
ATO / tax, custom reports, audit log and app log.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from app_theme import configure_tags, LABEL_MUTED, SIDEBAR_BG, SIDEBAR_SELECT_BG, SIDEBAR_SELECT_FG, SIDEBAR_FG
import csv
from datetime import datetime
from pathlib import Path
from smart_clipboard import bind_treeview_clipboard
from date_utils import DateEntry, display_to_storage, storage_to_display
from app_log import get_logger, log_path as _log_path

_log = get_logger('reports')


class ReportsTab:
    def __init__(self, parent_notebook, ds, settings_fn, currency_fn):
        """
        ds           : DataStore
        settings_fn  : callable() -> settings dict
        currency_fn  : callable() -> currency symbol string
        """
        self.ds = ds
        self.settings_fn = settings_fn
        self.currency_fn = currency_fn

        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text='Reports')
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        # Outer horizontal pane: sidebar | content
        outer = tk.PanedWindow(self.frame, orient='horizontal',
                               sashrelief='flat', sashwidth=4, bg='#cccccc')
        outer.pack(fill='both', expand=True)

        # --- Left sidebar: report list ---
        sidebar = ttk.Frame(outer, width=140)
        outer.add(sidebar, stretch='never', minsize=120)

        ttk.Label(sidebar, text='Reports', font=('Segoe UI', 9, 'bold'),
                  foreground=LABEL_MUTED).pack(anchor='w', padx=8, pady=(8, 4))

        sidebar.configure(style='Sidebar.TFrame')
        self._report_list = tk.Listbox(sidebar, selectmode='single', activestyle='none',
                                       relief='flat', bd=0, highlightthickness=0,
                                       font=('Segoe UI', 9), exportselection=False,
                                       bg=SIDEBAR_BG, fg=SIDEBAR_FG,
                                       selectbackground=SIDEBAR_SELECT_BG,
                                       selectforeground=SIDEBAR_SELECT_FG)
        self._report_list.pack(fill='both', expand=True, padx=4, pady=(0, 8))

        report_names = ['Summary', 'Invoices', 'Ledger',
                        'ATO / Tax', 'Custom Report',
                        'Audit Log', 'App Log']
        for name in report_names:
            self._report_list.insert('end', f'  {name}')
        self._report_list.bind('<<ListboxSelect>>', self._on_report_selected)

        # --- Right content area: one frame per report, stacked ---
        content = ttk.Frame(outer)
        outer.add(content, stretch='always')

        self._report_frames = {}
        self._report_panels = {}

        # Build each report as a child Frame of content (all stacked, only one visible)
        for name in report_names:
            f = ttk.Frame(content)
            f.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._report_frames[name] = f

        # Build content inside each frame (using a fake Notebook-like approach)
        class _FakeNb:
            """Quacks like a Notebook.add() but just raises the frame."""
            def __init__(self_inner, target):
                self_inner._f = target
            def add(self_inner, child_frame, **kw):
                pass  # child_frame IS the target frame — already added

        self._build_summary_tab(_FakeNb(None), frame_override=self._report_frames['Summary'])
        self._build_invoice_tab(_FakeNb(None), frame_override=self._report_frames['Invoices'])
        self._build_ledger_tab(_FakeNb(None), frame_override=self._report_frames['Ledger'])

        self._build_ato_tab(_FakeNb(None), frame_override=self._report_frames['ATO / Tax'])
        self._build_custom_report_tab(_FakeNb(None), frame_override=self._report_frames['Custom Report'])
        self._build_audit_tab(_FakeNb(None), frame_override=self._report_frames['Audit Log'])
        self._build_applog_tab(_FakeNb(None), frame_override=self._report_frames['App Log'])

        # Show first report by default
        self._report_list.selection_set(0)
        self._show_report('Summary')

    def _on_report_selected(self, event=None):
        sel = self._report_list.curselection()
        if not sel:
            return
        names = ['Summary', 'Invoices', 'Ledger',
                 'ATO / Tax', 'Custom Report',
                 'Audit Log', 'App Log']
        self._show_report(names[sel[0]])

    def _show_report(self, name):
        for n, f in self._report_frames.items():
            f.lower() if n != name else f.lift()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_tree(self, parent, cols, widths, height=16):
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(frame, columns=cols, show='headings', height=height)
        for c in cols:
            tree.heading(c, text=c.replace('_', ' ').title())
            tree.column(c, width=widths.get(c, 100), anchor='w')
        sb = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        sbx = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
        tree.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        sbx.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        bind_treeview_clipboard(tree, frame)
        return frame, tree

    def _export_tree(self, tree, filename_hint):
        path = filedialog.asksaveasfilename(
            title='Export Report',
            initialfile=filename_hint,
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('All', '*.*')])
        if not path:
            return
        cols = tree['columns']
        rows = [tree.item(i, 'values') for i in tree.get_children()]
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
        messagebox.showinfo('Exported', f'Saved to {path}')

    # ------------------------------------------------------------------
    # Business Summary
    # ------------------------------------------------------------------
    def _build_summary_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        self._summary_text = tk.Text(frame, width=80, height=30, state='disabled',
                                     font=('Courier', 10))
        sb = ttk.Scrollbar(frame, orient='vertical', command=self._summary_text.yview)
        self._summary_text.configure(yscrollcommand=sb.set)
        self._summary_text.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        sb.pack(side='right', fill='y', pady=8)

        btn_row = ttk.Frame(frame)
        btn_row.pack(side='bottom', fill='x', padx=8, pady=4)
        ttk.Button(btn_row, text='Refresh Summary', command=self._refresh_summary).pack(side='left', padx=3)
        ttk.Button(btn_row, text='Export PDF\u2026',  command=self._export_summary_pdf).pack(side='left', padx=3)
        ttk.Button(btn_row, text='Export CSV\u2026',  command=self._export_summary_csv).pack(side='left', padx=3)

    def _refresh_summary(self):
        sym = self.currency_fn()
        invoices = self.ds.read_invoices()
        ledger   = self.ds.read_ledger()

        # Invoice stats
        total_invoiced = sum(_safe_float(r.get('total')) for r in invoices)
        total_paid     = sum(_safe_float(r.get('total')) for r in invoices if r.get('paid', '').lower() in ('yes', 'true', '1'))
        total_unpaid   = total_invoiced - total_paid
        inv_count      = len(invoices)
        paid_count     = sum(1 for r in invoices if r.get('paid', '').lower() in ('yes', 'true', '1'))

        # Ledger stats
        ledger_in  = sum(_safe_float(r.get('amount')) for r in ledger if r.get('type') == 'in')
        ledger_out = sum(_safe_float(r.get('amount')) for r in ledger if r.get('type') == 'out')

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        lines = [
            f'BUSINESS SUMMARY  —  generated {now}',
            '=' * 52,
            '',
            'INVOICING',
            f'  Total invoices:      {inv_count}',
            f'  Total invoiced:      {sym}{total_invoiced:.2f}',
            f'  Paid ({paid_count}):           {sym}{total_paid:.2f}',
            f'  Outstanding:         {sym}{total_unpaid:.2f}',
            '',
            'LEDGER (non-invoice)',
            f'  Money in:            {sym}{ledger_in:.2f}',
            f'  Money out:           {sym}{ledger_out:.2f}',
            f'  Net:                 {sym}{ledger_in - ledger_out:.2f}',
            '',
            'COMBINED INCOME',
            f'  Invoice paid + in:   {sym}{total_paid + ledger_in:.2f}',
            f'  Total expenditure:   {sym}{ledger_out:.2f}',
            f'  Net position:        {sym}{total_paid + ledger_in - ledger_out:.2f}',
        ]

        self._summary_text.config(state='normal')
        self._summary_text.delete('1.0', 'end')
        self._summary_text.insert('1.0', '\n'.join(lines))
        self._summary_text.config(state='disabled')

    # ------------------------------------------------------------------
    # Invoice report
    # ------------------------------------------------------------------
    def _build_invoice_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        # Filter
        flt = ttk.Frame(frame)
        flt.pack(fill='x', padx=8, pady=4)
        ttk.Label(flt, text='Status:').pack(side='left')
        self._inv_status_var = tk.StringVar(value='All')
        ttk.Combobox(flt, textvariable=self._inv_status_var,
                     values=['All', 'Paid', 'Unpaid'], state='readonly', width=10).pack(side='left', padx=4)
        self._inv_status_var.trace_add('write', lambda *_: self._refresh_invoices())
        ttk.Button(flt, text='Export PDF…', command=self._export_invoices_pdf).pack(side='right', padx=4)
        ttk.Button(flt, text='Export CSV', command=lambda: self._export_tree(
            self._inv_tree, 'invoices_report.csv')).pack(side='right', padx=4)
        ttk.Button(flt, text='Refresh', command=self._refresh_invoices).pack(side='right')

        cols = ('invoice_number', 'invoice_date', 'due_date', 'client_name',
                'subtotal', 'gst', 'total', 'paid', 'paid_date', 'payment_note')
        widths = {'invoice_number': 80, 'invoice_date': 90, 'due_date': 90,
                  'client_name': 160, 'subtotal': 80, 'gst': 70,
                  'total': 80, 'paid': 60, 'paid_date': 90, 'payment_note': 180}
        tf, self._inv_tree = self._make_tree(frame, cols, widths)
        tf.pack(fill='both', expand=True, padx=8, pady=4)
        configure_tags(self._inv_tree, ['paid', 'unpaid'])

        self._inv_total_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._inv_total_var, foreground=LABEL_MUTED).pack(anchor='e', padx=8)

    def _refresh_invoices(self):
        for i in self._inv_tree.get_children():
            self._inv_tree.delete(i)
        sym = self.currency_fn()
        status_filter = self._inv_status_var.get()
        rows = self.ds.read_invoices()
        total = 0.0
        for r in reversed(rows):
            is_paid = r.get('paid', '').lower() in ('yes', 'true', '1')
            if status_filter == 'Paid' and not is_paid:
                continue
            if status_filter == 'Unpaid' and is_paid:
                continue
            amt = _safe_float(r.get('total'))
            total += amt
            tag = 'paid' if is_paid else 'unpaid'
            self._inv_tree.insert('', 'end', tags=(tag,), values=(
                r.get('invoice_number', ''), r.get('invoice_date', ''),
                r.get('due_date', ''), r.get('client_name', ''),
                f"{sym}{_safe_float(r.get('subtotal')):.2f}",
                f"{sym}{_safe_float(r.get('gst')):.2f}",
                f"{sym}{amt:.2f}",
                'Yes' if is_paid else 'No',
                r.get('paid_date', ''), r.get('payment_note', ''),
            ))
        self._inv_total_var.set(f'Shown total: {sym}{total:.2f}')

    # ------------------------------------------------------------------
    # Ledger report
    # ------------------------------------------------------------------
    def _build_ledger_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        flt = ttk.Frame(frame)
        flt.pack(fill='x', padx=8, pady=4)
        self._led_type_var = tk.StringVar(value='All')
        ttk.Combobox(flt, textvariable=self._led_type_var,
                     values=['All', 'in', 'out'], state='readonly', width=8).pack(side='left', padx=4)
        self._led_type_var.trace_add('write', lambda *_: self._refresh_ledger())
        ttk.Button(flt, text='Export PDF…', command=self._export_ledger_pdf).pack(side='right', padx=4)
        ttk.Button(flt, text='Export CSV', command=lambda: self._export_tree(
            self._led_tree, 'ledger_report.csv')).pack(side='right', padx=4)
        ttk.Button(flt, text='Refresh', command=self._refresh_ledger).pack(side='right')

        cols = ('date', 'type', 'category', 'description', 'amount', 'reference', 'notes')
        widths = {'date': 90, 'type': 50, 'category': 130, 'description': 200,
                  'amount': 90, 'reference': 110, 'notes': 200}
        tf, self._led_tree = self._make_tree(frame, cols, widths)
        tf.pack(fill='both', expand=True, padx=8, pady=4)
        configure_tags(self._led_tree, ['in', 'out'])

        self._led_total_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._led_total_var, foreground=LABEL_MUTED).pack(anchor='e', padx=8)

    def _refresh_ledger(self):
        for i in self._led_tree.get_children():
            self._led_tree.delete(i)
        sym = self.currency_fn()
        type_filter = self._led_type_var.get()
        rows = self.ds.read_ledger()
        total_in = total_out = 0.0
        for r in rows:
            rtype = r.get('type', '')
            if type_filter != 'All' and rtype != type_filter:
                continue
            amt = _safe_float(r.get('amount'))
            if rtype == 'in':
                total_in += amt
                display = f'+{sym}{amt:.2f}'
            else:
                total_out += amt
                display = f'-{sym}{amt:.2f}'
            self._led_tree.insert('', 'end', tags=(rtype,), values=(
                r.get('date', ''), rtype, r.get('category', ''),
                r.get('description', ''), display, r.get('reference', ''), r.get('notes', '')))
        self._led_total_var.set(
            f'In: {sym}{total_in:.2f}   Out: {sym}{total_out:.2f}   Net: {sym}{total_in - total_out:.2f}')

    # ------------------------------------------------------------------
    # Audit log (CSV-backed structured log)
    # ------------------------------------------------------------------
    def _build_audit_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        flt = ttk.Frame(frame)
        flt.pack(fill='x', padx=8, pady=4)
        ttk.Label(flt, text='Filter:').pack(side='left')
        self._audit_filter_var = tk.StringVar()
        ttk.Entry(flt, textvariable=self._audit_filter_var, width=24).pack(side='left', padx=4)
        self._audit_filter_var.trace_add('write', lambda *_: self._refresh_audit())
        ttk.Button(flt, text='Export PDF…', command=self._export_audit_pdf).pack(side='right', padx=4)
        ttk.Button(flt, text='Export CSV', command=lambda: self._export_tree(
            self._audit_tree, 'audit_log.csv')).pack(side='right', padx=4)
        ttk.Button(flt, text='Refresh', command=self._refresh_audit).pack(side='right')

        cols = ('timestamp', 'action', 'table', 'record_id', 'detail')
        widths = {'timestamp': 140, 'action': 150, 'table': 100,
                  'record_id': 70, 'detail': 380}
        tf, self._audit_tree = self._make_tree(frame, cols, widths, height=20)
        tf.pack(fill='both', expand=True, padx=8, pady=4)

    def _refresh_audit(self):
        for i in self._audit_tree.get_children():
            self._audit_tree.delete(i)
        query = self._audit_filter_var.get().strip().lower()
        rows = self.ds.read_audit()
        for r in reversed(rows):
            if query and not any(query in str(v).lower() for v in r.values()):
                continue
            self._audit_tree.insert('', 'end', values=(
                r.get('timestamp', ''), r.get('action', ''),
                r.get('table', ''), r.get('record_id', ''),
                r.get('detail', '')))

    # ------------------------------------------------------------------
    # App log (plain-text rotating log file)
    # ------------------------------------------------------------------
    def _build_applog_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=8, pady=4)
        ttk.Button(toolbar, text='Refresh', command=self._refresh_applog).pack(side='left', padx=3)
        ttk.Button(toolbar, text='Export Log…', command=self._export_applog).pack(side='left', padx=3)
        self._applog_path_var = tk.StringVar(value='')
        ttk.Label(toolbar, textvariable=self._applog_path_var,
                  foreground='#555').pack(side='left', padx=8)

        # Level filter
        ttk.Label(toolbar, text='Level:').pack(side='right', padx=(8, 2))
        self._applog_level_var = tk.StringVar(value='All')
        ttk.Combobox(toolbar, textvariable=self._applog_level_var,
                     values=['All', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                     state='readonly', width=9).pack(side='right')
        self._applog_level_var.trace_add('write', lambda *_: self._refresh_applog())

        # Search
        ttk.Label(toolbar, text='Search:').pack(side='right', padx=(12, 2))
        self._applog_search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self._applog_search_var, width=20).pack(side='right')
        self._applog_search_var.trace_add('write', lambda *_: self._refresh_applog())

        txt_frame = ttk.Frame(frame)
        txt_frame.pack(fill='both', expand=True, padx=8, pady=4)
        self._applog_text = tk.Text(txt_frame, wrap='none', state='disabled',
                                    font=('Consolas', 9), background='#1e1e1e',
                                    foreground='#d4d4d4', insertbackground='white')
        vsb = ttk.Scrollbar(txt_frame, orient='vertical', command=self._applog_text.yview)
        hsb = ttk.Scrollbar(txt_frame, orient='horizontal', command=self._applog_text.xview)
        self._applog_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._applog_text.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        txt_frame.rowconfigure(0, weight=1)
        txt_frame.columnconfigure(0, weight=1)

        # Colour tags
        self._applog_text.tag_configure('DEBUG',    foreground='#888')
        self._applog_text.tag_configure('INFO',     foreground='#9cdcfe')
        self._applog_text.tag_configure('WARNING',  foreground='#dcdcaa')
        self._applog_text.tag_configure('ERROR',    foreground='#f48771')
        self._applog_text.tag_configure('CRITICAL', foreground='#ff5370', font=('Consolas', 9, 'bold'))

    def _refresh_applog(self):
        path = _log_path()
        self._applog_path_var.set(str(path) if path else 'Log file not found')
        self._applog_text.configure(state='normal')
        self._applog_text.delete('1.0', 'end')
        if not path or not Path(path).exists():
            self._applog_text.insert('end', 'Log file not available yet.\n')
            self._applog_text.configure(state='disabled')
            return

        level_filter = self._applog_level_var.get()
        search_term  = self._applog_search_var.get().strip().lower()
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        show_levels = (set(levels[levels.index(level_filter):]) if level_filter != 'All'
                       else set(levels))

        try:
            text = Path(path).read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            self._applog_text.insert('end', f'Cannot read log: {e}\n')
            self._applog_text.configure(state='disabled')
            return

        for line in text.splitlines():
            matched_level = next((lv for lv in levels if f'  {lv}' in line or f'  {lv} ' in line), 'INFO')
            if matched_level not in show_levels:
                continue
            if search_term and search_term not in line.lower():
                continue
            self._applog_text.insert('end', line + '\n', matched_level)

        self._applog_text.see('end')
        self._applog_text.configure(state='disabled')

    def _export_applog(self):
        path = _log_path()
        if not path or not Path(path).exists():
            messagebox.showinfo('No log', 'Log file not available.', parent=self.frame)
            return
        dest = filedialog.asksaveasfilename(
            title='Export App Log',
            defaultextension='.log',
            filetypes=[('Log files', '*.log'), ('Text files', '*.txt'), ('All files', '*.*')],
            initialfile='invoicer.log',
            parent=self.frame,
        )
        if not dest:
            return
        try:
            import shutil as _sh
            _sh.copy2(path, dest)
            messagebox.showinfo('Exported', f'Log saved to:\n{dest}', parent=self.frame)
        except Exception as e:
            messagebox.showerror('Export failed', str(e), parent=self.frame)

    # ------------------------------------------------------------------
    # PDF preview launchers
    # ------------------------------------------------------------------
    def _get_tree_rows(self, tree):
        """Extract all rows from a treeview as list of lists of str."""
        return [list(tree.item(iid, 'values')) for iid in tree.get_children()]

    def _open_preview(self, title, columns, rows, summary_lines=None):
        from report_preview import ReportPreviewDialog
        ReportPreviewDialog(
            parent        = self.frame,
            title         = title,
            columns       = columns,
            rows          = rows,
            summary_lines = summary_lines,
            settings      = self.settings_fn(),
        )

    def _export_summary_csv(self):
        content = self._summary_text.get('1.0', 'end').strip()
        path = filedialog.asksaveasfilename(
            title='Export Summary',
            initialfile='business_summary.csv',
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('Text', '*.txt'), ('All', '*.*')],
            parent=self.frame)
        if not path:
            return
        lines = content.splitlines()
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Business Summary'])
                for line in lines:
                    writer.writerow([line])
            messagebox.showinfo('Exported', f'Saved to {path}', parent=self.frame)
        except Exception as e:
            messagebox.showerror('Export failed', str(e), parent=self.frame)

    def _export_summary_pdf(self):
        content = self._summary_text.get('1.0', 'end').strip()
        lines   = content.splitlines()
        rows    = [[line] for line in lines]
        self._open_preview('Business Summary', ['Summary'], rows)

    def _export_invoices_pdf(self):
        rows = self._get_tree_rows(self._inv_tree)
        cols = ['Invoice #', 'Date', 'Due Date', 'Client',
                'Subtotal', 'GST', 'Total', 'Paid', 'Paid Date', 'Payment Note']
        total_text = self._inv_total_var.get()
        self._open_preview('Invoice Report', cols, rows,
                           summary_lines=[total_text] if total_text else None)

    def _export_ledger_pdf(self):
        rows = self._get_tree_rows(self._led_tree)
        cols = ['Date', 'Type', 'Category', 'Description', 'Amount', 'Reference', 'Notes']
        summary_text = self._led_total_var.get()
        self._open_preview('Ledger Report', cols, rows,
                           summary_lines=[summary_text] if summary_text else None)

    def _export_audit_pdf(self):
        rows = self._get_tree_rows(self._audit_tree)
        cols = ['Timestamp', 'Action', 'Table', 'Record ID', 'Detail']
        self._open_preview('Audit Log', cols, rows)

    # ------------------------------------------------------------------
    # ATO / Tax report
    # ------------------------------------------------------------------
    def _build_ato_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        # ---- header info ----
        info = ttk.LabelFrame(frame, text='ATO / Tax Report  (Australia — BAS-ready GST summary)')
        info.pack(fill='x', padx=8, pady=(8, 2))
        ttk.Label(info, text=(
            'Covers invoices and ledger entries for the selected financial year / quarter.\n'
            'GST figures are taken from invoice GST fields.  Review before lodging your BAS.'
        ), foreground='#555').pack(anchor='w', padx=8, pady=4)

        # ---- filter row ----
        flt = ttk.Frame(frame)
        flt.pack(fill='x', padx=8, pady=4)

        ttk.Label(flt, text='Financial year:').pack(side='left')
        current_year = datetime.now().year
        fy_options = [f'{y}-{y+1}' for y in range(current_year - 5, current_year + 2)]
        self._ato_fy_var = tk.StringVar(value=f'{current_year-1}-{current_year}'
                                        if datetime.now().month < 7
                                        else f'{current_year}-{current_year+1}')
        ttk.Combobox(flt, textvariable=self._ato_fy_var, values=fy_options,
                     state='readonly', width=10).pack(side='left', padx=4)

        ttk.Label(flt, text='Period:').pack(side='left', padx=(12, 2))
        self._ato_period_var = tk.StringVar(value='Full Year')
        ttk.Combobox(flt, textvariable=self._ato_period_var,
                     values=['Full Year', 'Q1 Jul-Sep', 'Q2 Oct-Dec', 'Q3 Jan-Mar', 'Q4 Apr-Jun'],
                     state='readonly', width=14).pack(side='left', padx=4)

        ttk.Button(flt, text='Run Report', command=self._refresh_ato).pack(side='left', padx=8)
        ttk.Button(flt, text='Export CSV…', command=self._export_ato_csv).pack(side='right', padx=4)
        ttk.Button(flt, text='Export PDF…', command=self._export_ato_pdf).pack(side='right', padx=4)

        # ---- BAS summary cards ----
        cards = ttk.LabelFrame(frame, text='BAS Summary')
        cards.pack(fill='x', padx=8, pady=4)
        self._ato_card_frame = ttk.Frame(cards)
        self._ato_card_frame.pack(fill='x', padx=4, pady=6)

        # ---- detail tabs inside ATO panel ----
        self._ato_nb = ttk.Notebook(frame)
        self._ato_nb.pack(fill='both', expand=True, padx=8, pady=4)

        # GST collected tab
        gst_col_f = ttk.Frame(self._ato_nb)
        self._ato_nb.add(gst_col_f, text='GST Collected (Sales)')
        cols = ('date', 'invoice_number', 'client', 'subtotal', 'gst', 'total', 'paid')
        widths = {'date': 90, 'invoice_number': 80, 'client': 180,
                  'subtotal': 90, 'gst': 75, 'total': 90, 'paid': 50}
        tf, self._ato_gst_col_tree = self._make_tree(gst_col_f, cols, widths)
        tf.pack(fill='both', expand=True)
        self._ato_gst_col_lbl = tk.StringVar()
        ttk.Label(gst_col_f, textvariable=self._ato_gst_col_lbl,
                  foreground=LABEL_MUTED).pack(anchor='e', padx=8)

        # GST paid (expenses) tab
        gst_paid_f = ttk.Frame(self._ato_nb)
        self._ato_nb.add(gst_paid_f, text='GST Paid (Expenses)')
        cols2 = ('date', 'category', 'description', 'amount_excl_gst', 'gst_paid', 'total', 'reference')
        widths2 = {'date': 90, 'category': 130, 'description': 220,
                   'amount_excl_gst': 100, 'gst_paid': 80, 'total': 90, 'reference': 110}
        tf2, self._ato_gst_paid_tree = self._make_tree(gst_paid_f, cols2, widths2)
        for c in cols2:
            self._ato_gst_paid_tree.heading(c, text=c.replace('_', ' ').title())
        tf2.pack(fill='both', expand=True)
        self._ato_gst_paid_lbl = tk.StringVar()
        ttk.Label(gst_paid_f, textvariable=self._ato_gst_paid_lbl,
                  foreground=LABEL_MUTED).pack(anchor='e', padx=8)

        # Income & Expense summary tab
        ie_f = ttk.Frame(self._ato_nb)
        self._ato_nb.add(ie_f, text='Income & Expense Summary')
        self._ato_ie_text = tk.Text(ie_f, font=('Courier', 10), state='disabled', width=80, height=28)
        sb_ie = ttk.Scrollbar(ie_f, orient='vertical', command=self._ato_ie_text.yview)
        self._ato_ie_text.configure(yscrollcommand=sb_ie.set)
        self._ato_ie_text.pack(side='left', fill='both', expand=True, padx=8, pady=6)
        sb_ie.pack(side='right', fill='y', pady=6)

        # Category breakdown tab
        cat_f = ttk.Frame(self._ato_nb)
        self._ato_nb.add(cat_f, text='By Category')
        cols3 = ('category', 'type', 'count', 'total_excl_gst', 'gst_component', 'total_incl_gst')
        widths3 = {'category': 180, 'type': 60, 'count': 50,
                   'total_excl_gst': 110, 'gst_component': 100, 'total_incl_gst': 110}
        tf3, self._ato_cat_tree = self._make_tree(cat_f, cols3, widths3)
        for c in cols3:
            self._ato_cat_tree.heading(c, text=c.replace('_', ' ').title())
        tf3.pack(fill='both', expand=True)

        self._ato_rows_cache = []   # for CSV export

    def _ato_date_range(self):
        """Return (start_str, end_str) YYYY-MM-DD for the selected FY + period."""
        fy   = self._ato_fy_var.get()          # e.g. '2024-2025'
        per  = self._ato_period_var.get()
        try:
            y1, y2 = int(fy[:4]), int(fy[5:])
        except Exception:
            y1, y2 = datetime.now().year - 1, datetime.now().year
        quarter_ranges = {
            'Q1 Jul-Sep': (f'{y1}-07-01', f'{y1}-09-30'),
            'Q2 Oct-Dec': (f'{y1}-10-01', f'{y1}-12-31'),
            'Q3 Jan-Mar': (f'{y2}-01-01', f'{y2}-03-31'),
            'Q4 Apr-Jun': (f'{y2}-04-01', f'{y2}-06-30'),
        }
        if per in quarter_ranges:
            return quarter_ranges[per]
        return f'{y1}-07-01', f'{y2}-06-30'

    def _refresh_ato(self):
        sym       = self.currency_fn()
        settings  = self.settings_fn()
        gst_rate  = float(settings.get('gst_rate', 0.10))
        start, end = self._ato_date_range()

        invoices = [r for r in self.ds.read_invoices()
                    if start <= r.get('invoice_date', '') <= end]
        ledger   = [r for r in self.ds.read_ledger()
                    if start <= r.get('date', '') <= end]

        # ---- GST Collected (sales) ----
        for i in self._ato_gst_col_tree.get_children():
            self._ato_gst_col_tree.delete(i)
        total_sales_excl = total_gst_col = total_sales_incl = 0.0
        for r in sorted(invoices, key=lambda x: x.get('invoice_date', '')):
            sub = _safe_float(r.get('subtotal'))
            gst = _safe_float(r.get('gst'))
            tot = _safe_float(r.get('total'))
            if tot == 0 and sub > 0:
                tot = sub + gst
            is_paid = r.get('paid', '').lower() in ('yes', 'true', '1')
            total_sales_excl += sub
            total_gst_col    += gst
            total_sales_incl += tot
            self._ato_gst_col_tree.insert('', 'end', values=(
                r.get('invoice_date', ''), r.get('invoice_number', ''),
                r.get('client_name', ''),
                f'{sym}{sub:.2f}', f'{sym}{gst:.2f}', f'{sym}{tot:.2f}',
                'Yes' if is_paid else 'No',
            ))
        self._ato_gst_col_lbl.set(
            f'Sales (excl. GST): {sym}{total_sales_excl:.2f}   '
            f'GST Collected: {sym}{total_gst_col:.2f}   '
            f'Total (incl. GST): {sym}{total_sales_incl:.2f}')

        # ---- GST Paid (expenses from ledger 'out' entries) ----
        for i in self._ato_gst_paid_tree.get_children():
            self._ato_gst_paid_tree.delete(i)
        total_exp_incl = total_gst_paid = 0.0
        exp_by_cat = {}
        for r in sorted([x for x in ledger if x.get('type') == 'out'],
                        key=lambda x: x.get('date', '')):
            tot  = _safe_float(r.get('amount'))
            # Back-calculate GST component (assumes 1/11 rule for GST-inclusive amounts)
            gst  = round(tot * gst_rate / (1 + gst_rate), 2)
            excl = round(tot - gst, 2)
            cat  = r.get('category', 'Uncategorised')
            total_exp_incl += tot
            total_gst_paid += gst
            exp_by_cat.setdefault(cat, {'count': 0, 'excl': 0.0, 'gst': 0.0, 'incl': 0.0})
            exp_by_cat[cat]['count'] += 1
            exp_by_cat[cat]['excl']  += excl
            exp_by_cat[cat]['gst']   += gst
            exp_by_cat[cat]['incl']  += tot
            self._ato_gst_paid_tree.insert('', 'end', values=(
                r.get('date', ''), cat,
                r.get('description', ''),
                f'{sym}{excl:.2f}', f'{sym}{gst:.2f}', f'{sym}{tot:.2f}',
                r.get('reference', ''),
            ))
        self._ato_gst_paid_lbl.set(
            f'Expenses (incl. GST): {sym}{total_exp_incl:.2f}   '
            f'GST Credits (1/11 rule): {sym}{total_gst_paid:.2f}   '
            f'Expenses (excl. GST): {sym}{total_exp_incl - total_gst_paid:.2f}')

        # ---- Income & Expense summary text ----
        net_gst = total_gst_col - total_gst_paid
        income_in = sum(_safe_float(r.get('amount')) for r in ledger if r.get('type') == 'in')
        fy = self._ato_fy_var.get()
        per = self._ato_period_var.get()
        abn = settings.get('business_abn', '')
        biz = settings.get('business_name', '')
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        lines = [
            f'ATO TAX REPORT  —  {biz}',
            f'ABN: {abn}' if abn else 'ABN: (not set — configure in Settings)',
            f'Period: {per}  |  Financial Year: {fy}',
            f'Date range: {start}  to  {end}',
            f'Generated: {now}',
            '=' * 58,
            '',
            'INCOME',
            f'  Invoice sales (excl. GST):     {sym}{total_sales_excl:>10.2f}',
            f'  GST collected on sales:        {sym}{total_gst_col:>10.2f}',
            f'  Other income (ledger in):      {sym}{income_in:>10.2f}',
            f'  Total income (excl. GST):      {sym}{total_sales_excl + income_in:>10.2f}',
            '',
            'EXPENSES',
            f'  Total expenses (incl. GST):    {sym}{total_exp_incl:>10.2f}',
            f'  GST credits (1/11 rule):       {sym}{total_gst_paid:>10.2f}',
            f'  Total expenses (excl. GST):    {sym}{total_exp_incl - total_gst_paid:>10.2f}',
            '',
            'BAS SUMMARY (GST)',
            f'  1A  GST on sales:              {sym}{total_gst_col:>10.2f}',
            f'  1B  GST credits (purchases):   {sym}{total_gst_paid:>10.2f}',
            f'  Net GST {"payable" if net_gst >= 0 else "refundable"}:              {sym}{abs(net_gst):>10.2f}',
            '',
            'NET POSITION',
            f'  Total income (excl. GST):      {sym}{total_sales_excl + income_in:>10.2f}',
            f'  Total expenses (excl. GST):    {sym}{total_exp_incl - total_gst_paid:>10.2f}',
            f'  Net profit / (loss):           {sym}{total_sales_excl + income_in - (total_exp_incl - total_gst_paid):>10.2f}',
            '',
            'NOTE: This report is a guide only. Verify with your accountant.',
            'GST credits use the 1/11 rule on ledger "out" entries (assumes GST-inclusive).',
        ]
        self._ato_ie_text.configure(state='normal')
        self._ato_ie_text.delete('1.0', 'end')
        self._ato_ie_text.insert('1.0', '\n'.join(lines))
        self._ato_ie_text.configure(state='disabled')

        # ---- Category breakdown ----
        for i in self._ato_cat_tree.get_children():
            self._ato_cat_tree.delete(i)
        # Sales as one row
        self._ato_cat_tree.insert('', 'end', values=(
            'Invoice Sales', 'in', len(invoices),
            f'{sym}{total_sales_excl:.2f}', f'{sym}{total_gst_col:.2f}',
            f'{sym}{total_sales_incl:.2f}',
        ))
        for cat, d in sorted(exp_by_cat.items()):
            self._ato_cat_tree.insert('', 'end', values=(
                cat, 'out', d['count'],
                f'{sym}{d["excl"]:.2f}', f'{sym}{d["gst"]:.2f}',
                f'{sym}{d["incl"]:.2f}',
            ))

        # ---- BAS cards ----
        for w in self._ato_card_frame.winfo_children():
            w.destroy()
        card_data = [
            ('1A  GST on Sales',      f'{sym}{total_gst_col:.2f}',    '#2e7d32'),
            ('1B  GST Credits',       f'{sym}{total_gst_paid:.2f}',   '#c62828'),
            ('Net GST',               f'{sym}{abs(net_gst):.2f} {"payable" if net_gst >= 0 else "refund"}',
                                      '#1565c0' if net_gst < 0 else '#e65100'),
            ('Total Income (excl.)',  f'{sym}{total_sales_excl + income_in:.2f}', '#2e7d32'),
            ('Total Expenses (excl.)',f'{sym}{total_exp_incl - total_gst_paid:.2f}', '#c62828'),
            ('Net Profit / (Loss)',   f'{sym}{total_sales_excl + income_in - (total_exp_incl - total_gst_paid):.2f}',
                                      '#1565c0'),
        ]
        for col_idx, (label, value, colour) in enumerate(card_data):
            card = tk.Frame(self._ato_card_frame, relief='solid', bd=1, padx=10, pady=6, bg='#f9f9f9')
            card.grid(row=0, column=col_idx, padx=5, pady=4, sticky='n')
            tk.Label(card, text=label, font=('Segoe UI', 8), bg='#f9f9f9', fg='#555').pack(anchor='w')
            tk.Label(card, text=value, font=('Segoe UI', 10, 'bold'), bg='#f9f9f9', fg=colour).pack(anchor='w')

        self._ato_rows_cache = {
            'gst_collected': [(r.get('invoice_date',''), r.get('invoice_number',''),
                               r.get('client_name',''),
                               _safe_float(r.get('subtotal')), _safe_float(r.get('gst')),
                               _safe_float(r.get('total')))
                              for r in invoices],
            'summary': lines,
        }

    def _export_ato_csv(self):
        if not hasattr(self, '_ato_rows_cache') or not self._ato_rows_cache:
            messagebox.showinfo('No data', 'Run the report first.', parent=self.frame)
            return
        path = filedialog.asksaveasfilename(
            title='Export ATO Report CSV',
            initialfile='ato_tax_report.csv',
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv'), ('All', '*.*')],
            parent=self.frame)
        if not path:
            return
        sym = self.currency_fn()
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['ATO / TAX REPORT'])
                w.writerow([''])
                w.writerow(['--- SUMMARY ---'])
                for line in self._ato_rows_cache.get('summary', []):
                    w.writerow([line])
                w.writerow([''])
                w.writerow(['--- GST COLLECTED ---'])
                w.writerow(['Date', 'Invoice #', 'Client', 'Subtotal', 'GST', 'Total'])
                for row in self._ato_rows_cache.get('gst_collected', []):
                    w.writerow([row[0], row[1], row[2],
                                f'{sym}{row[3]:.2f}', f'{sym}{row[4]:.2f}', f'{sym}{row[5]:.2f}'])
            messagebox.showinfo('Exported', f'Saved to {path}', parent=self.frame)
        except Exception as e:
            messagebox.showerror('Export failed', str(e), parent=self.frame)

    def _export_ato_pdf(self):
        if not hasattr(self, '_ato_rows_cache') or not self._ato_rows_cache:
            messagebox.showinfo('No data', 'Run the report first.', parent=self.frame)
            return
        rows = [list(self._ato_gst_col_tree.item(i, 'values'))
                for i in self._ato_gst_col_tree.get_children()]
        cols = ['Date', 'Invoice #', 'Client', 'Subtotal', 'GST', 'Total', 'Paid']
        summary = self._ato_rows_cache.get('summary', [])
        self._open_preview('ATO / Tax Report', cols, rows, summary_lines=summary[:20])

    # ------------------------------------------------------------------
    # Custom Report builder
    # ------------------------------------------------------------------
    def _build_custom_report_tab(self, nb, frame_override=None):
        frame = frame_override if frame_override is not None else ttk.Frame(nb)

        # ---- top: data source + field chooser ----
        cfg = ttk.LabelFrame(frame, text='Report Builder')
        cfg.pack(fill='x', padx=8, pady=(8, 2))

        # Row 1: data source
        r1 = ttk.Frame(cfg)
        r1.pack(fill='x', padx=8, pady=4)
        ttk.Label(r1, text='Data source:').pack(side='left')
        self._cust_src_var = tk.StringVar(value='Invoices')
        src_cb = ttk.Combobox(r1, textvariable=self._cust_src_var,
                               values=['Invoices', 'Ledger'],
                               state='readonly', width=22)
        src_cb.pack(side='left', padx=4)
        src_cb.bind('<<ComboboxSelected>>', lambda e: self._cust_refresh_fields())
        ttk.Button(r1, text='Load fields →', command=self._cust_refresh_fields).pack(side='left', padx=4)

        # Row 2: date range
        r2 = ttk.Frame(cfg)
        r2.pack(fill='x', padx=8, pady=2)
        ttk.Label(r2, text='Date from:').pack(side='left')
        self._cust_from_var = tk.StringVar()
        DateEntry(r2, textvariable=self._cust_from_var, width=12).pack(side='left', padx=4)
        ttk.Label(r2, text='to:').pack(side='left')
        self._cust_to_var = tk.StringVar()
        DateEntry(r2, textvariable=self._cust_to_var, width=12).pack(side='left', padx=4)
        ttk.Label(r2, text='(DD/MM/YYYY or blank for all)', foreground='grey').pack(side='left')

        # Row 3: text filter
        r3 = ttk.Frame(cfg)
        r3.pack(fill='x', padx=8, pady=2)
        ttk.Label(r3, text='Filter (any field contains):').pack(side='left')
        self._cust_filter_var = tk.StringVar()
        ttk.Entry(r3, textvariable=self._cust_filter_var, width=24).pack(side='left', padx=4)
        ttk.Label(r3, text='Group by:').pack(side='left', padx=(12, 2))
        self._cust_group_var = tk.StringVar(value='(none)')
        self._cust_group_cb = ttk.Combobox(r3, textvariable=self._cust_group_var,
                                            values=['(none)'], state='readonly', width=20)
        self._cust_group_cb.pack(side='left', padx=4)

        # Row 4: field selector
        field_row = ttk.LabelFrame(cfg, text='Select columns (Ctrl+click for multiple)')
        field_row.pack(fill='x', padx=8, pady=4)
        fl = ttk.Frame(field_row)
        fl.pack(fill='x', padx=4, pady=4)
        self._cust_field_lb = tk.Listbox(fl, selectmode='multiple', height=4,
                                          exportselection=False)
        sb_f = ttk.Scrollbar(fl, orient='vertical', command=self._cust_field_lb.yview)
        self._cust_field_lb.configure(yscrollcommand=sb_f.set)
        self._cust_field_lb.pack(side='left', fill='x', expand=True)
        sb_f.pack(side='right', fill='y')

        ttk.Label(field_row, text='Leave all blank to include every column.',
                  foreground='grey').pack(anchor='w', padx=4, pady=(0, 4))

        # Row 5: run buttons
        run_row = ttk.Frame(cfg)
        run_row.pack(fill='x', padx=8, pady=(2, 6))
        ttk.Button(run_row, text='Run Report',    command=self._run_custom_report).pack(side='left', padx=3)
        ttk.Button(run_row, text='Export CSV…',  command=self._export_custom_csv).pack(side='left', padx=3)
        ttk.Button(run_row, text='Export PDF…',  command=self._export_custom_pdf).pack(side='left', padx=3)

        # ---- preset save/load ----
        preset_row = ttk.Frame(frame)
        preset_row.pack(fill='x', padx=8, pady=(0, 2))
        ttk.Label(preset_row, text='Preset:').pack(side='left')
        self._cust_preset_var = tk.StringVar()
        self._cust_preset_cb = ttk.Combobox(preset_row, textvariable=self._cust_preset_var,
                                             values=[], width=24)
        self._cust_preset_cb.pack(side='left', padx=4)
        ttk.Button(preset_row, text='Save preset',   command=self._save_custom_preset).pack(side='left', padx=3)
        ttk.Button(preset_row, text='Load preset',   command=self._load_custom_preset).pack(side='left', padx=3)
        ttk.Button(preset_row, text='Delete preset', command=self._delete_custom_preset).pack(side='left', padx=3)
        ttk.Label(preset_row, text='(presets stored as custom_reports.json)',
                  foreground='grey').pack(side='left', padx=8)

        self._cust_presets = self._load_custom_presets_file()
        self._update_preset_list()

        # ---- results ----
        self._cust_result_frame = ttk.Frame(frame)
        self._cust_result_frame.pack(fill='both', expand=True, padx=8, pady=4)
        self._cust_tree = None
        self._cust_result_lbl = tk.StringVar()
        ttk.Label(frame, textvariable=self._cust_result_lbl, foreground=LABEL_MUTED
                  ).pack(anchor='e', padx=8)

        # Prime field list
        self._cust_refresh_fields()

    # ---- Custom report helpers ----
    _CUST_FIELDS = {
        'Invoices': ['invoice_number', 'invoice_date', 'due_date', 'client_name',
                     'subtotal', 'gst', 'total', 'paid', 'paid_date', 'payment_note'],
        'Ledger':   ['date', 'type', 'category', 'description', 'amount', 'reference', 'notes'],
    }
    _DATE_FIELD = {
        'Invoices':   'invoice_date',
        'Ledger':     'date',
    }

    def _cust_refresh_fields(self):
        src = self._cust_src_var.get()
        fields = self._CUST_FIELDS.get(src, [])
        self._cust_field_lb.delete(0, 'end')
        for f in fields:
            self._cust_field_lb.insert('end', f)
        self._cust_group_cb['values'] = ['(none)'] + fields
        self._cust_group_var.set('(none)')

    def _cust_get_raw_rows(self):
        src = self._cust_src_var.get()
        if src == 'Invoices':
            return self.ds.read_invoices()
        if src == 'Ledger':
            return self.ds.read_ledger()
        return []

    def _run_custom_report(self):
        src     = self._cust_src_var.get()
        all_fields = self._CUST_FIELDS.get(src, [])
        sel_idx = self._cust_field_lb.curselection()
        chosen  = [all_fields[i] for i in sel_idx] if sel_idx else list(all_fields)
        date_field = self._DATE_FIELD.get(src, '')
        frm = display_to_storage(self._cust_from_var.get().strip())
        to  = display_to_storage(self._cust_to_var.get().strip())
        flt = self._cust_filter_var.get().strip().lower()
        grp = self._cust_group_var.get()

        rows = self._cust_get_raw_rows()

        # Date filter
        if frm or to:
            filtered = []
            for r in rows:
                dval = r.get(date_field, '')
                if frm and dval < frm:
                    continue
                if to and dval > to:
                    continue
                filtered.append(r)
            rows = filtered

        # Text filter
        if flt:
            rows = [r for r in rows
                    if any(flt in str(r.get(f, '')).lower() for f in all_fields)]

        # Group by
        if grp and grp != '(none)':
            from collections import defaultdict
            groups = defaultdict(list)
            for r in rows:
                groups[r.get(grp, '')].append(r)
            grouped_rows = []
            for key in sorted(groups.keys()):
                grouped_rows.append({f: (f'=== {key} ===' if f == grp else '') for f in chosen})
                grouped_rows.extend(groups[key])
            rows = grouped_rows

        # Build treeview
        for w in self._cust_result_frame.winfo_children():
            w.destroy()
        widths = {f: max(80, len(f) * 9) for f in chosen}
        tf, self._cust_tree = self._make_tree(self._cust_result_frame, chosen, widths)
        tf.pack(fill='both', expand=True)
        sym = self.currency_fn()
        for r in rows:
            vals = []
            for f in chosen:
                v = r.get(f, '')
                if f in self._DATE_FIELD.values():
                    v = storage_to_display(str(v))
                if f in ('subtotal', 'gst', 'total', 'amount') and v not in ('', None):
                    try:
                        v = f'{sym}{float(v):.2f}'
                    except (ValueError, TypeError):
                        pass
                vals.append(str(v))
            self._cust_tree.insert('', 'end', values=tuple(vals))
        self._cust_result_lbl.set(f'{len(rows)} row(s)  |  Columns: {len(chosen)}')

    def _export_custom_csv(self):
        if not self._cust_tree:
            messagebox.showinfo('No data', 'Run the report first.', parent=self.frame)
            return
        self._export_tree(self._cust_tree, 'custom_report.csv')

    def _export_custom_pdf(self):
        if not self._cust_tree:
            messagebox.showinfo('No data', 'Run the report first.', parent=self.frame)
            return
        rows = self._get_tree_rows(self._cust_tree)
        cols = [c.replace('_', ' ').title() for c in self._cust_tree['columns']]
        summary = self._cust_result_lbl.get()
        self._open_preview('Custom Report', cols, rows, summary_lines=[summary] if summary else None)

    # ---- Preset persistence ----
    def _presets_path(self):
        return self.ds.data_dir / 'custom_reports.json'

    def _load_custom_presets_file(self) -> dict:
        import json as _json
        p = self._presets_path()
        if p.exists():
            try:
                return _json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _save_custom_presets_file(self):
        import json as _json
        p = self._presets_path()
        p.write_text(_json.dumps(self._cust_presets, indent=2), encoding='utf-8')

    def _update_preset_list(self):
        self._cust_preset_cb['values'] = sorted(self._cust_presets.keys())

    def _save_custom_preset(self):
        name = self._cust_preset_var.get().strip()
        if not name:
            from tkinter import simpledialog
            name = simpledialog.askstring('Save Preset', 'Preset name:', parent=self.frame)
        if not name:
            return
        sel_idx = self._cust_field_lb.curselection()
        src = self._cust_src_var.get()
        all_fields = self._CUST_FIELDS.get(src, [])
        self._cust_presets[name] = {
            'source':  src,
            'fields':  [all_fields[i] for i in sel_idx],
            'from':    self._cust_from_var.get().strip(),
            'to':      self._cust_to_var.get().strip(),
            'filter':  self._cust_filter_var.get().strip(),
            'group_by': self._cust_group_var.get(),
        }
        self._save_custom_presets_file()
        self._update_preset_list()
        self._cust_preset_var.set(name)
        messagebox.showinfo('Saved', f'Preset "{name}" saved.', parent=self.frame)

    def _load_custom_preset(self):
        name = self._cust_preset_var.get().strip()
        if name not in self._cust_presets:
            messagebox.showinfo('Not found', 'Select a preset name first.', parent=self.frame)
            return
        p = self._cust_presets[name]
        self._cust_src_var.set(p.get('source', 'Invoices'))
        self._cust_refresh_fields()
        all_fields = self._CUST_FIELDS.get(p.get('source', 'Invoices'), [])
        self._cust_field_lb.selection_clear(0, 'end')
        for f in p.get('fields', []):
            if f in all_fields:
                self._cust_field_lb.selection_set(all_fields.index(f))
        self._cust_from_var.set(p.get('from', ''))
        self._cust_to_var.set(p.get('to', ''))
        self._cust_filter_var.set(p.get('filter', ''))
        self._cust_group_var.set(p.get('group_by', '(none)'))

    def _delete_custom_preset(self):
        name = self._cust_preset_var.get().strip()
        if name not in self._cust_presets:
            messagebox.showinfo('Not found', 'Select a preset name first.', parent=self.frame)
            return
        if not messagebox.askyesno('Delete', f'Delete preset "{name}"?', parent=self.frame):
            return
        del self._cust_presets[name]
        self._save_custom_presets_file()
        self._update_preset_list()
        self._cust_preset_var.set('')

    # ------------------------------------------------------------------
    def refresh(self):
        self._refresh_summary()
        self._refresh_invoices()
        self._refresh_ledger()
        self._refresh_audit()
        self._refresh_applog()


def _safe_float(v):
    try:
        return float(v or 0)
    except (ValueError, TypeError):
        return 0.0
