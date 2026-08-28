"""
health_checks.py
================
Pure-function business health checks.  No Tkinter dependency.

Usage
-----
    from health_checks import compute_health_prompts

    alerts = compute_health_prompts(ds, settings)
    # alerts -> list of dicts:
    #   { 'level': 'warn'|'info'|'ok',
    #     'category': str,
    #     'message': str,
    #     'detail': str }   # optional extra detail
"""

from datetime import date, timedelta


def _f(v) -> float:
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def compute_health_prompts(ds, settings: dict = None, today: date = None) -> list:
    """
    Run all health checks against the data store.

    Parameters
    ----------
    ds       : DataStore instance
    settings : app settings dict
    today    : override today's date (for testing)

    Returns
    -------
    list of alert dicts sorted by level (warn first, then info, then ok).
    Each dict has keys: level, category, message, detail (may be '').
    """
    settings = settings or {}
    today    = today or date.today()
    alerts   = []

    def warn(cat, msg, detail=''):
        alerts.append({'level': 'warn', 'category': cat,
                       'message': msg, 'detail': detail})

    def info(cat, msg, detail=''):
        alerts.append({'level': 'info', 'category': cat,
                       'message': msg, 'detail': detail})

    def ok(cat, msg):
        alerts.append({'level': 'ok', 'category': cat, 'message': msg, 'detail': ''})

    today_s  = today.isoformat()
    ago30_s  = (today - timedelta(days=30)).isoformat()

    # ----------------------------------------------------------------
    # 1. Overdue invoices (past due date, not paid/cancelled/void)
    # ----------------------------------------------------------------
    try:
        invoices = ds.read_invoices()
    except Exception:
        invoices = []

    overdue = [inv for inv in invoices
               if inv.get('invoice_status', '') not in ('paid', 'cancelled', 'void')
               and inv.get('due_date', '') and inv.get('due_date', '') < today_s]
    if overdue:
        names = ', '.join(inv.get('invoice_number', '?') for inv in overdue[:5])
        warn('Invoices', f'{len(overdue)} overdue invoice(s)',
             f'{names}{"…" if len(overdue) > 5 else ""}')
    else:
        ok('Invoices', 'No overdue invoices')

    # ----------------------------------------------------------------
    # 2. Unpaid invoices older than 30 days (but not past due)
    # ----------------------------------------------------------------
    old_unpaid = [inv for inv in invoices
                  if inv.get('invoice_status', '') in ('unpaid', 'partial')
                  and inv.get('invoice_date', '') < ago30_s
                  and inv not in overdue]
    if old_unpaid:
        names = ', '.join(inv.get('invoice_number', '?') for inv in old_unpaid[:5])
        info('Invoices', f'{len(old_unpaid)} unpaid invoice(s) older than 30 days',
             names)

    # ----------------------------------------------------------------
    # 3. Uncategorised ledger expenses
    # ----------------------------------------------------------------
    try:
        ledger = ds.read_ledger()
    except Exception:
        ledger = []

    uncat = [r for r in ledger
             if r.get('deleted', '') != '1'
             and r.get('type') == 'out'
             and not (r.get('category') or '').strip()]
    if uncat:
        warn('Ledger', f'{len(uncat)} uncategorised expense(s)',
             'Open Ledger tab and assign categories')
    else:
        ok('Ledger', 'All expenses categorised')

    # ----------------------------------------------------------------
    # 4. Expense ledger entries missing receipts
    # ----------------------------------------------------------------
    no_receipt = [r for r in ledger
                  if r.get('deleted', '') != '1'
                  and r.get('type') == 'out'
                  and not (r.get('receipt_path') or '').strip()]
    if no_receipt:
        info('Ledger', f'{len(no_receipt)} expense(s) without receipt attachment')

    # ----------------------------------------------------------------
    # Sort: warn → info → ok
    # ----------------------------------------------------------------
    order = {'warn': 0, 'info': 1, 'ok': 2}
    alerts.sort(key=lambda a: order.get(a['level'], 9))
    return alerts
