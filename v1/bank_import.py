"""
bank_import.py
==============
Bank statement CSV import and invoice payment matching.

Supports common Australian bank CSV formats:
  - NAB: Date, Amount, Description, ...
  - CBA: Date, Amount, Description, Balance
  - ANZ: Date, Amount, Description, Reference, Balance
  - Westpac: Date, Narration, Debit, Credit, Balance
  - Generic: first date-like col, first numeric col, first text col
"""

import csv
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from pathlib import Path

from date_utils import storage_to_display, display_to_storage, fmt_display, parse_date


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _try_parse_amount(val: str) -> float | None:
    """Return float or None."""
    if not val:
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except ValueError:
        return None


def _detect_format(headers: list[str]) -> str:
    """Return bank format hint based on header names."""
    h = [c.strip().lower() for c in headers]
    if 'narration' in h and ('debit' in h or 'credit' in h):
        return 'westpac'
    if 'date' in h and 'amount' in h:
        return 'standard'     # NAB / CBA / ANZ all have Date + Amount
    return 'generic'


def parse_bank_csv(path: str) -> list[dict]:
    """
    Parse a bank statement CSV.  Returns a list of dicts with keys:
      date        (YYYY-MM-DD storage format)
      amount      (float, positive = credit/money-in)
      description (str)
      reference   (str)
      raw         (original row dict)
    Only credits (amount > 0) are returned — debits are irrelevant for payment matching.
    Raises ValueError with a human-readable message on failure.
    """
    path = Path(path)
    # Try to read with utf-8-sig first, fall back to latin-1
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            with open(path, newline='', encoding=enc) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Could not decode file — try saving as UTF-8 CSV.")

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    fmt = _detect_format(list(reader.fieldnames))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV contains no data rows.")

    results = []
    for raw in rows:
        raw = {k.strip(): v.strip() for k, v in raw.items() if k}

        if fmt == 'westpac':
            date_str  = raw.get('Date', '')
            desc      = raw.get('Narration', '')
            ref       = raw.get('Cheque Number', raw.get('Reference', ''))
            credit    = _try_parse_amount(raw.get('Credit', ''))
            debit     = _try_parse_amount(raw.get('Debit', ''))
            if credit and credit > 0:
                amount = credit
            elif debit and debit > 0:
                amount = -debit
            else:
                continue
        else:
            # standard / generic — find date, amount, description columns
            date_str = ''
            for col in ('Date', 'date', 'Transaction Date', 'Effective Date'):
                if col in raw and raw[col]:
                    date_str = raw[col]
                    break
            if not date_str:
                # fallback: first column that looks like a date
                for v in raw.values():
                    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', v):
                        date_str = v
                        break

            amt_raw = raw.get('Amount', raw.get('amount', ''))
            if not amt_raw:
                # try Credit/Debit split
                credit = _try_parse_amount(raw.get('Credit', raw.get('credit', '')))
                debit  = _try_parse_amount(raw.get('Debit',  raw.get('debit',  '')))
                if credit and credit > 0:
                    amount = credit
                elif debit and debit > 0:
                    amount = -debit
                else:
                    continue
            else:
                amount = _try_parse_amount(amt_raw)
                if amount is None:
                    continue

            desc = raw.get('Description', raw.get('Narrative', raw.get('Narration',
                   raw.get('Merchant Name', raw.get('description', '')))))
            ref  = raw.get('Reference', raw.get('Cheque', raw.get('reference', '')))

        if amount is None or amount <= 0:
            continue          # skip debits / zero rows

        parsed_date = parse_date(date_str)
        if not parsed_date:
            continue

        results.append({
            'date':        parsed_date.strftime('%Y-%m-%d'),
            'amount':      amount,
            'description': str(desc).strip(),
            'reference':   str(ref).strip(),
            'raw':         raw,
        })

    return results


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def auto_match(transactions: list[dict], invoices: list[dict],
               existing_payments: list[dict],
               tolerance_days: int = 3) -> list[dict]:
    """
    For each transaction attempt to find an unpaid/partial invoice where:
      - amount matches invoice total or invoice balance (within $0.01)
      - transaction date is within tolerance_days of invoice due_date or invoice_date

    Returns list of dicts:
      tx           : the transaction dict
      invoice      : matched invoice dict or None
      confidence   : 'high' | 'low' | 'none'
      already_paid : bool — invoice already fully paid
    """
    def _balance(inv):
        total = float(inv.get('total', 0) or 0)
        paid  = sum(float(p.get('amount', 0) or 0)
                    for p in existing_payments
                    if p.get('invoice_number') == inv.get('invoice_number'))
        return max(round(total - paid, 2), 0.0)

    results = []
    for tx in transactions:
        tx_amt  = tx['amount']
        tx_date = parse_date(tx['date'])
        best_inv  = None
        best_conf = 'none'

        for inv in invoices:
            status = inv.get('invoice_status', '').lower()
            if status in ('paid', 'cancelled', 'void'):
                continue

            inv_total   = float(inv.get('total', 0) or 0)
            inv_balance = _balance(inv)

            # Amount must match total OR remaining balance
            amt_match = (abs(tx_amt - inv_total) < 0.02 or
                         (inv_balance > 0 and abs(tx_amt - inv_balance) < 0.02))
            if not amt_match:
                continue

            # Date proximity
            due_date = parse_date(inv.get('due_date', ''))
            inv_date = parse_date(inv.get('invoice_date', ''))
            close = False
            for ref_date in filter(None, [due_date, inv_date]):
                if tx_date and abs((tx_date - ref_date).days) <= tolerance_days:
                    close = True
                    break

            confidence = 'high' if (amt_match and close) else 'low'
            # Prefer high confidence, then any match
            if best_conf == 'none' or (best_conf == 'low' and confidence == 'high'):
                best_inv  = inv
                best_conf = confidence

        results.append({
            'tx':           tx,
            'invoice':      best_inv,
            'confidence':   best_conf,
            'already_paid': best_inv is not None and
                            best_inv.get('invoice_status', '').lower() == 'paid',
        })
    return results


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class BankImportDialog(tk.Toplevel):
    """
    Import a bank statement CSV, auto-match credits to outstanding invoices,
    allow manual matching, then apply matched payments to payments.csv + ledger.
    """

    def __init__(self, parent, ds, sym='$'):
        super().__init__(parent)
        self.ds  = ds
        self.sym = sym
        self.title('Import Bank Statement')
        self.geometry('1100x620')
        self.resizable(True, True)
        self.grab_set()
        self._match_rows = []      # list of match dicts
        self._inv_map    = {}      # invoice_number -> invoice row
        self._build()
        self.wait_window(self)

    # ------------------------------------------------------------------
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=(10, 4))

        ttk.Label(top, text='Bank Statement CSV:').pack(side='left')
        self._file_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._file_var, width=55).pack(side='left', padx=4)
        ttk.Button(top, text='Browse…', command=self._browse).pack(side='left')
        ttk.Button(top, text='Load & Match', command=self._load).pack(side='left', padx=8)

        ttk.Label(top, text='Match window (days):').pack(side='left', padx=(16, 2))
        self._days_var = tk.StringVar(value='3')
        ttk.Spinbox(top, from_=0, to=30, textvariable=self._days_var, width=4).pack(side='left')

        # ---- Treeview ----
        cols = ('date', 'amount', 'description', 'reference', 'match_inv', 'match_amt', 'conf')
        self._tree = ttk.Treeview(self, columns=cols, show='headings', selectmode='browse')
        hdrs = [('date', 90, 'Date'), ('amount', 85, 'Amount'),
                ('description', 240, 'Description'), ('reference', 110, 'Reference'),
                ('match_inv', 80, 'Invoice #'), ('match_amt', 85, 'Invoice Total'),
                ('conf', 70, 'Match')]
        for col, w, lbl in hdrs:
            self._tree.heading(col, text=lbl)
            self._tree.column(col, width=w, anchor='w' if col in ('description','reference') else 'center')
        self._tree.column('amount',    anchor='e')
        self._tree.column('match_amt', anchor='e')

        self._tree.tag_configure('high',      background='#d4edda', foreground='#155724')
        self._tree.tag_configure('low',       background='#fff3cd', foreground='#856404')
        self._tree.tag_configure('none',      background='#f8d7da', foreground='#721c24')
        self._tree.tag_configure('skip',      background='#e2e3e5', foreground='#6c757d')

        sb = ttk.Scrollbar(self, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscroll=sb.set)
        self._tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=4)
        sb.pack(side='left', fill='y', pady=4)

        # ---- Right panel ----
        rp = ttk.Frame(self)
        rp.pack(side='right', fill='y', padx=10, pady=4)

        ttk.Label(rp, text='Manual Match', font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0, 2))
        ttk.Label(rp, text='Invoice #:').pack(anchor='w')
        self._manual_var = tk.StringVar()
        self._manual_cb  = ttk.Combobox(rp, textvariable=self._manual_var, width=14, state='normal')
        self._manual_cb.pack(anchor='w', pady=(0, 4))
        ttk.Button(rp, text='Assign Match', command=self._manual_assign).pack(fill='x', pady=2)
        ttk.Button(rp, text='Clear Match',  command=self._clear_match).pack(fill='x', pady=2)

        ttk.Separator(rp, orient='horizontal').pack(fill='x', pady=8)

        self._status_var = tk.StringVar(value='Load a CSV to begin.')
        ttk.Label(rp, textvariable=self._status_var, wraplength=160,
                  justify='left').pack(anchor='w')

        ttk.Separator(rp, orient='horizontal').pack(fill='x', pady=8)

        ttk.Button(rp, text='Apply Matched Payments',
                   command=self._apply, style='Accent.TButton').pack(fill='x', pady=2)
        ttk.Button(rp, text='Close', command=self.destroy).pack(fill='x', pady=2)

    # ------------------------------------------------------------------
    def _browse(self):
        path = filedialog.askopenfilename(
            title='Open Bank Statement CSV',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            parent=self)
        if path:
            self._file_var.set(path)

    def _load(self):
        path = self._file_var.get().strip()
        if not path:
            messagebox.showwarning('No file', 'Browse to a bank statement CSV first.', parent=self)
            return
        try:
            days = int(self._days_var.get() or 3)
        except ValueError:
            days = 3
        try:
            transactions = parse_bank_csv(path)
        except Exception as e:
            messagebox.showerror('Parse error', str(e), parent=self)
            return

        invoices = self.ds.read_invoices()
        payments = self.ds.read_payments()
        self._inv_map = {r['invoice_number']: r for r in invoices}

        # Populate combobox
        unpaid_nums = [r['invoice_number'] for r in invoices
                       if r.get('invoice_status', 'unpaid').lower() not in ('paid', 'cancelled', 'void')]
        self._manual_cb['values'] = unpaid_nums

        self._match_rows = auto_match(transactions, invoices, payments, tolerance_days=days)
        self._render()
        n_high = sum(1 for m in self._match_rows if m['confidence'] == 'high')
        n_low  = sum(1 for m in self._match_rows if m['confidence'] == 'low')
        n_none = sum(1 for m in self._match_rows if m['confidence'] == 'none')
        self._status_var.set(
            f'{len(transactions)} credits found.\n\n'
            f'✅ {n_high} high-confidence\n'
            f'⚠️  {n_low} low-confidence\n'
            f'❌ {n_none} unmatched\n\n'
            f'Select a row to manually assign.')

    def _render(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        sym = self.sym
        for i, m in enumerate(self._match_rows):
            tx   = m['tx']
            inv  = m['invoice']
            conf = m['confidence']
            tag  = conf
            inv_num = inv['invoice_number'] if inv else ''
            inv_tot = f"{sym}{float(inv.get('total',0)):.2f}" if inv else ''
            conf_lbl = {'high': '✅ High', 'low': '⚠ Low', 'none': '❌ None'}.get(conf, conf)
            self._tree.insert('', 'end', iid=str(i), tags=(tag,), values=(
                storage_to_display(tx['date']),
                f"{sym}{tx['amount']:.2f}",
                tx['description'],
                tx['reference'],
                inv_num,
                inv_tot,
                conf_lbl,
            ))

    # ------------------------------------------------------------------
    def _selected_idx(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _manual_assign(self):
        idx = self._selected_idx()
        if idx is None:
            messagebox.showinfo('No selection', 'Select a bank row first.', parent=self)
            return
        inv_num = self._manual_var.get().strip()
        if not inv_num:
            messagebox.showinfo('No invoice', 'Enter or select an invoice number.', parent=self)
            return
        inv = self._inv_map.get(inv_num)
        if not inv:
            messagebox.showwarning('Not found', f'Invoice #{inv_num} not found.', parent=self)
            return
        self._match_rows[idx]['invoice']    = inv
        self._match_rows[idx]['confidence'] = 'low'
        self._render()
        self._tree.selection_set(str(idx))
        self._tree.see(str(idx))

    def _clear_match(self):
        idx = self._selected_idx()
        if idx is None:
            return
        self._match_rows[idx]['invoice']    = None
        self._match_rows[idx]['confidence'] = 'none'
        self._render()
        self._tree.selection_set(str(idx))

    # ------------------------------------------------------------------
    def _apply(self):
        matched = [(i, m) for i, m in enumerate(self._match_rows)
                   if m['invoice'] is not None and m['confidence'] != 'none']
        if not matched:
            messagebox.showinfo('Nothing to apply',
                'No matched rows to apply.  Use Manual Match or load another file.',
                parent=self)
            return

        # Confirm
        if not messagebox.askyesno(
                'Confirm',
                f'Apply {len(matched)} payment(s) to invoices?\n\n'
                'Each matched transaction will be recorded as a payment and '
                'posted to the ledger.',
                parent=self):
            return

        applied = 0
        skipped = 0
        for _, m in matched:
            tx  = m['tx']
            inv = m['invoice']
            inv_num = inv['invoice_number']

            # Check not already paid
            existing = self.ds.payments_for_invoice(inv_num)
            already  = sum(float(p.get('amount', 0) or 0) for p in existing)
            inv_total = float(inv.get('total', 0) or 0)
            if already >= inv_total:
                skipped += 1
                continue

            self.ds.append_payment({
                'invoice_number': inv_num,
                'date':           tx['date'],
                'amount':         f"{tx['amount']:.2f}",
                'method':         'Bank Transfer',
                'reference':      tx.get('reference', ''),
                'notes':          f"Bank import: {tx.get('description', '')}",
            })
            self.ds.recalculate_invoice_status(inv_num)

            # Auto-post to ledger
            client = inv.get('client_name', '')
            self.ds.append_ledger({
                'date':        tx['date'],
                'type':        'in',
                'category':    'Invoice Payment',
                'description': f"Payment — Invoice {inv_num} — {client}",
                'amount':      f"{tx['amount']:.2f}",
                'reference':   inv_num,
                'notes':       f"Bank import: {tx.get('description', '')}",
            })
            applied += 1

        msg = f'{applied} payment(s) applied.'
        if skipped:
            msg += f'\n{skipped} skipped (already fully paid).'
        messagebox.showinfo('Done', msg, parent=self)

        # Grey out applied rows
        for i, m in matched:
            self._tree.item(str(i), tags=('skip',))
        self._status_var.set(f'{applied} applied, {skipped} skipped.')
