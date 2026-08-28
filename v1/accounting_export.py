"""
accounting_export.py
====================
Export invoice and ledger data to Xero and MYOB compatible CSV formats.

Supported exports
-----------------
  build_xero_invoices_csv   — Xero Accounts Receivable import (Sales)
  build_xero_spend_money_csv — Xero Spend Money / Accounts Payable import
  build_myob_sales_csv      — MYOB AccountRight Sales import
  build_myob_purchases_csv  — MYOB AccountRight Purchases import

All functions write to a file path (str or Path) and return the row count written.
"""

import csv
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v) -> float:
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _xero_date(iso: str) -> str:
    """YYYY-MM-DD  →  DD/MM/YYYY  (Xero AU format)."""
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return iso or ''


def _myob_date(iso: str) -> str:
    """YYYY-MM-DD  →  DD/MM/YYYY  (MYOB AU format)."""
    return _xero_date(iso)


def _filter_date(rows: list, field: str, start: str, end: str) -> list:
    if start:
        rows = [r for r in rows if r.get(field, '') >= start]
    if end:
        rows = [r for r in rows if r.get(field, '') <= end]
    return rows


# ---------------------------------------------------------------------------
# Xero — Accounts Receivable (invoices)
# ---------------------------------------------------------------------------
# Column reference: https://central.xero.com/s/article/Import-invoices-in-Xero
XERO_INVOICE_HEADERS = [
    '*ContactName', 'EmailAddress', 'POAddressLine1', 'POAddressLine2',
    'POAddressLine3', 'POAddressLine4', 'POCity', 'PORegion',
    'POPostalCode', 'POCountry',
    '*InvoiceNumber', '*InvoiceDate', '*DueDate', 'Total',
    'InventoryItemCode', 'Description', '*Quantity', '*UnitAmount',
    'Discount', '*AccountCode', '*TaxType',
    'TaxAmount', 'TrackingName1', 'TrackingOption1',
    'TrackingName2', 'TrackingOption2', 'Currency',
]

XERO_TAX_INCLUSIVE  = 'GST on Income'
XERO_TAX_NONE       = 'GST Free Income'
XERO_ACCOUNT_SALES  = '200'    # default Xero Sales account


def build_xero_invoices_csv(path, invoices: list, settings: dict = None,
                             start: str = '', end: str = '') -> int:
    """
    Write a Xero Accounts Receivable import CSV.

    Each invoice becomes one row (single line item — the subtotal/GST/total).
    Cancelled/void invoices are skipped.
    """
    settings = settings or {}
    gst_reg  = str(settings.get('gst_registered', 'yes')).lower() in ('yes', 'true', '1')
    acct     = settings.get('xero_sales_account', XERO_ACCOUNT_SALES)
    currency = settings.get('currency_code', 'AUD')

    inv_list = _filter_date(
        [r for r in invoices if r.get('invoice_status', '') not in ('cancelled', 'void')],
        'invoice_date', start, end)

    path = Path(path)
    count = 0
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=XERO_INVOICE_HEADERS, extrasaction='ignore')
        w.writeheader()
        for inv in inv_list:
            subtotal = _f(inv.get('subtotal', 0))
            gst      = _f(inv.get('gst', 0))
            total    = _f(inv.get('total', 0))
            if total == 0 and subtotal > 0:
                total = subtotal + gst
            tax_type = XERO_TAX_INCLUSIVE if (gst_reg and gst > 0) else XERO_TAX_NONE
            row = {
                '*ContactName':    inv.get('client_name', ''),
                '*InvoiceNumber':  inv.get('invoice_number', ''),
                '*InvoiceDate':    _xero_date(inv.get('invoice_date', '')),
                '*DueDate':        _xero_date(inv.get('due_date', '')),
                'Total':           f'{total:.2f}',
                'Description':     inv.get('notes', ''),
                '*Quantity':       '1',
                '*UnitAmount':     f'{subtotal:.2f}',
                '*AccountCode':    acct,
                '*TaxType':        tax_type,
                'TaxAmount':       f'{gst:.2f}',
                'Currency':        currency,
            }
            w.writerow(row)
            count += 1
    return count


# ---------------------------------------------------------------------------
# Xero — Spend Money (ledger expenses)
# ---------------------------------------------------------------------------
XERO_SPEND_HEADERS = [
    '*ContactName', 'EmailAddress', 'POAddressLine1',
    '*Date', '*Amount', 'Payee', 'Description', 'Reference',
    '*AccountCode', '*TaxType', 'TaxAmount', 'TrackingName1',
    'TrackingOption1', 'Currency',
]

XERO_TAX_GST_EXPENSE = 'GST on Expenses'
XERO_TAX_NONE_EXP    = 'GST Free Expenses'
XERO_ACCOUNT_EXPENSE = '420'    # default General Expenses


def build_xero_spend_money_csv(path, ledger: list, settings: dict = None,
                                start: str = '', end: str = '') -> int:
    """Write a Xero Spend Money import CSV from ledger 'out' rows."""
    settings = settings or {}
    gst_reg  = str(settings.get('gst_registered', 'yes')).lower() in ('yes', 'true', '1')
    gst_rate = _f(settings.get('gst_rate', 0.10))
    currency = settings.get('currency_code', 'AUD')

    rows = _filter_date(
        [r for r in ledger if r.get('type') == 'out' and r.get('deleted', '') != '1'],
        'date', start, end)

    # Map category to Xero account code using settings override or fallback
    acct_map = {}
    try:
        import json
        raw = settings.get('xero_account_map', '{}')
        acct_map = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass

    path = Path(path)
    count = 0
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=XERO_SPEND_HEADERS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            amount  = _f(r.get('amount', 0))
            cat     = r.get('category', '') or 'General'
            acct    = acct_map.get(cat, XERO_ACCOUNT_EXPENSE)
            gst_amt = round(amount * gst_rate / (1 + gst_rate), 2) if gst_reg else 0.0
            tax_type = XERO_TAX_GST_EXPENSE if (gst_reg and gst_amt > 0) else XERO_TAX_NONE_EXP
            row = {
                '*ContactName': cat,
                '*Date':        _xero_date(r.get('date', '')),
                '*Amount':      f'{amount:.2f}',
                'Payee':        r.get('reference', ''),
                'Description':  r.get('description', ''),
                'Reference':    r.get('reference', ''),
                '*AccountCode': acct,
                '*TaxType':     tax_type,
                'TaxAmount':    f'{gst_amt:.2f}',
                'Currency':     currency,
            }
            w.writerow(row)
            count += 1
    return count


# ---------------------------------------------------------------------------
# MYOB — Sales (invoices)
# ---------------------------------------------------------------------------
# Column reference: MYOB AccountRight Sales Import
MYOB_SALES_HEADERS = [
    'Co./Last Name', 'First Name', 'Addr 1 - Line 1',
    'Invoice #', 'Date', 'Due Date',
    'Item Number', 'Description', 'Quantity', 'Unit Price',
    'Discount', 'Total', 'Tax Code', 'Tax Amount',
    'Already Paid', 'Payment Method', 'Memo',
    'Account Number',
]

MYOB_ACCOUNT_INCOME = '4-0000'


def build_myob_sales_csv(path, invoices: list, settings: dict = None,
                          start: str = '', end: str = '') -> int:
    """Write a MYOB AccountRight Sales import CSV."""
    settings = settings or {}
    gst_reg  = str(settings.get('gst_registered', 'yes')).lower() in ('yes', 'true', '1')
    acct     = settings.get('myob_income_account', MYOB_ACCOUNT_INCOME)

    inv_list = _filter_date(
        [r for r in invoices if r.get('invoice_status', '') not in ('cancelled', 'void')],
        'invoice_date', start, end)

    path = Path(path)
    count = 0
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=MYOB_SALES_HEADERS, extrasaction='ignore')
        w.writeheader()
        for inv in inv_list:
            subtotal = _f(inv.get('subtotal', 0))
            gst      = _f(inv.get('gst', 0))
            total    = _f(inv.get('total', 0))
            if total == 0 and subtotal > 0:
                total = subtotal + gst
            tax_code = 'GST' if (gst_reg and gst > 0) else 'FRE'
            paid     = '1' if inv.get('invoice_status') == 'paid' else '0'
            row = {
                'Co./Last Name':  inv.get('client_name', ''),
                'Invoice #':      inv.get('invoice_number', ''),
                'Date':           _myob_date(inv.get('invoice_date', '')),
                'Due Date':       _myob_date(inv.get('due_date', '')),
                'Description':    inv.get('notes', ''),
                'Quantity':       '1',
                'Unit Price':     f'{subtotal:.2f}',
                'Total':          f'{total:.2f}',
                'Tax Code':       tax_code,
                'Tax Amount':     f'{gst:.2f}',
                'Already Paid':   paid,
                'Memo':           inv.get('notes', ''),
                'Account Number': acct,
            }
            w.writerow(row)
            count += 1
    return count


# ---------------------------------------------------------------------------
# MYOB — Purchases / Spend Money (ledger expenses)
# ---------------------------------------------------------------------------
MYOB_PURCHASES_HEADERS = [
    'Co./Last Name', 'First Name', 'Addr 1 - Line 1',
    'Invoice #', 'Date', 'Due Date',
    'Item Number', 'Description', 'Quantity', 'Unit Price',
    'Discount', 'Total', 'Tax Code', 'Tax Amount',
    'Memo', 'Account Number',
]

MYOB_ACCOUNT_EXPENSE = '6-0000'


def build_myob_purchases_csv(path, ledger: list, settings: dict = None,
                              start: str = '', end: str = '') -> int:
    """Write a MYOB AccountRight Purchases import CSV from ledger 'out' rows."""
    settings = settings or {}
    gst_reg  = str(settings.get('gst_registered', 'yes')).lower() in ('yes', 'true', '1')
    gst_rate = _f(settings.get('gst_rate', 0.10))
    acct     = settings.get('myob_expense_account', MYOB_ACCOUNT_EXPENSE)

    rows = _filter_date(
        [r for r in ledger if r.get('type') == 'out' and r.get('deleted', '') != '1'],
        'date', start, end)

    path = Path(path)
    count = 0
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=MYOB_PURCHASES_HEADERS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            amount   = _f(r.get('amount', 0))
            gst_amt  = round(amount * gst_rate / (1 + gst_rate), 2) if gst_reg else 0.0
            net_amt  = round(amount - gst_amt, 2)
            tax_code = 'GST' if (gst_reg and gst_amt > 0) else 'FRE'
            row = {
                'Co./Last Name':  r.get('category', 'Expense'),
                'Date':           _myob_date(r.get('date', '')),
                'Description':    r.get('description', ''),
                'Quantity':       '1',
                'Unit Price':     f'{net_amt:.2f}',
                'Total':          f'{amount:.2f}',
                'Tax Code':       tax_code,
                'Tax Amount':     f'{gst_amt:.2f}',
                'Memo':           r.get('notes', ''),
                'Account Number': acct,
            }
            w.writerow(row)
            count += 1
    return count
