"""
accountant_pack.py
==================
Build an Accountant PDF Report Pack — a single PDF containing:

  1. Cover page   (business name, ABN, FY, generated date)
  2. P&L Summary  (income, expenses, net profit)
  3. Invoice list (all invoices in the FY, with status + balance)
  4. Ledger       (categorised income & expense detail)
  5. ATO / BAS summary (GST collected, GST credits, net GST)

Usage
-----
    from accountant_pack import build_accountant_pack

    build_accountant_pack(
        path     = '/path/to/output.pdf',
        ds       = data_store_instance,
        settings = app_settings_dict,
        fy       = '2025-2026',           # e.g. '2025-2026'
    )
"""

from pathlib import Path
from datetime import datetime, date as _date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v) -> float:
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _fmt(v, sym='$') -> str:
    try:
        return f'{sym}{float(str(v).replace(",","").strip()):,.2f}'
    except (ValueError, TypeError):
        return str(v)


def _fy_dates(fy: str):
    """Return (start_str, end_str) in YYYY-MM-DD for an Aus financial year '2025-2026'."""
    try:
        parts = fy.replace('/', '-').split('-')
        y1, y2 = int(parts[0]), int(parts[-1])
    except Exception:
        y = datetime.now().year
        y1, y2 = (y - 1, y) if datetime.now().month < 7 else (y, y + 1)
    return f'{y1}-07-01', f'{y2}-06-30'


# ---------------------------------------------------------------------------
# Style factory
# ---------------------------------------------------------------------------

def _make_styles(hdr_col, acc_col, str_col):
    styles = getSampleStyleSheet()
    n = styles['Normal']

    def ps(name, **kw):
        return ParagraphStyle(name, parent=n, **kw)

    return {
        'h1':      ps('h1',  fontSize=22, fontName='Helvetica-Bold',
                       textColor=hdr_col, spaceAfter=4),
        'h2':      ps('h2',  fontSize=14, fontName='Helvetica-Bold',
                       textColor=hdr_col, spaceBefore=6, spaceAfter=3),
        'h3':      ps('h3',  fontSize=10, fontName='Helvetica-Bold',
                       textColor=acc_col, spaceBefore=4, spaceAfter=2),
        'body':    ps('body', fontSize=9),
        'small':   ps('small', fontSize=7.5),
        'bold9':   ps('bold9', fontSize=9, fontName='Helvetica-Bold'),
        'right9':  ps('right9', fontSize=9, fontName='Helvetica-Bold',
                       alignment=TA_RIGHT),
        'th':      ps('th', fontSize=8, fontName='Helvetica-Bold',
                       textColor=colors.white, alignment=TA_CENTER),
        'td':      ps('td', fontSize=8),
        'tdr':     ps('tdr', fontSize=8, alignment=TA_RIGHT),
        'tdb':     ps('tdb', fontSize=8, fontName='Helvetica-Bold'),
        'tdbr':    ps('tdbr', fontSize=8, fontName='Helvetica-Bold',
                       alignment=TA_RIGHT),
        'cover_sub': ps('cover_sub', fontSize=12, textColor=colors.HexColor('#555555')),
        'cover_label': ps('cover_label', fontSize=10, textColor=hdr_col,
                           fontName='Helvetica-Bold'),
    }


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _tbl_style(hdr_col, str_col):
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  hdr_col),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  8),
        ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, str_col]),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ])


def _footer_style(hdr_col):
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), hdr_col),
        ('TEXTCOLOR',     (0, 0), (-1, -1), colors.white),
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ALIGN',         (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ])


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _cover(story, styles, biz, abn, fy, start, end, prepared_by, hdr_col):
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph(biz or 'Your Business', styles['h1']))
    story.append(HRFlowable(width='100%', thickness=2, color=hdr_col))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph('ACCOUNTANT REPORT PACK', ParagraphStyle(
        'cp', parent=styles['body'], fontSize=16,
        fontName='Helvetica-Bold', textColor=hdr_col)))
    story.append(Spacer(1, 6 * mm))

    meta = [
        ('Financial Year', fy),
        ('Period',         f'{start}  to  {end}'),
        ('ABN',            abn or '(not set)'),
        ('Prepared by',    prepared_by or ''),
        ('Generated',      datetime.now().strftime('%d/%m/%Y %H:%M')),
    ]
    for label, value in meta:
        if not value:
            continue
        row_data = [[Paragraph(f'<b>{label}:</b>', styles['body']),
                     Paragraph(value, styles['body'])]]
        t = Table(row_data, colWidths=[45 * mm, 110 * mm])
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(t)

    story.append(Spacer(1, 10 * mm))
    toc_items = [
        '1.  P&L Summary',
        '2.  Invoice List',
        '3.  Ledger — Income',
        '4.  Ledger — Expenses',
        '5.  ATO / BAS Summary',
    ]
    story.append(Paragraph('<b>Contents</b>', styles['h3']))
    for item in toc_items:
        story.append(Paragraph(item, styles['body']))
    story.append(PageBreak())


def _section_header(story, styles, number, title, hdr_col):
    story.append(HRFlowable(width='100%', thickness=1.5, color=hdr_col))
    story.append(Paragraph(f'{number}.  {title}', styles['h2']))
    story.append(Spacer(1, 2 * mm))


def _pl_section(story, styles, invoices, ledger, sym, fy, start, end, hdr_col):
    _section_header(story, styles, 1, 'Profit & Loss Summary', hdr_col)

    inv_in_fy = [r for r in invoices
                 if start <= r.get('invoice_date', '') <= end
                 and r.get('invoice_status', '') not in ('cancelled', 'void')]
    led_in_fy = [r for r in ledger
                 if start <= r.get('date', '') <= end
                 and r.get('deleted', '') != '1']

    total_inv      = sum(_f(r.get('total')) for r in inv_in_fy)
    total_paid_inv = sum(_f(r.get('total')) for r in inv_in_fy
                         if r.get('invoice_status') == 'paid')
    total_income   = sum(_f(r.get('amount')) for r in led_in_fy if r.get('type') == 'in')
    total_expenses = sum(_f(r.get('amount')) for r in led_in_fy if r.get('type') == 'out')
    net_profit     = total_income - total_expenses

    rows = [
        [Paragraph('<b>Item</b>',  styles['th']), Paragraph('<b>Amount</b>', styles['th'])],
        [Paragraph('Total Invoiced (FY)',     styles['td']), Paragraph(_fmt(total_inv, sym),      styles['tdr'])],
        [Paragraph('Total Paid Invoices',     styles['td']), Paragraph(_fmt(total_paid_inv, sym), styles['tdr'])],
        [Paragraph('Outstanding',             styles['td']), Paragraph(_fmt(total_inv - total_paid_inv, sym), styles['tdr'])],
        [Paragraph('',                        styles['td']), Paragraph('',                        styles['tdr'])],
        [Paragraph('Ledger Income',           styles['td']), Paragraph(_fmt(total_income, sym),   styles['tdr'])],
        [Paragraph('Ledger Expenses',         styles['td']), Paragraph(_fmt(total_expenses, sym), styles['tdr'])],
        [Paragraph('<b>Net Profit</b>',       styles['tdb']), Paragraph(_fmt(net_profit, sym),    styles['tdbr'])],
    ]
    tbl = Table(rows, colWidths=[110 * mm, 40 * mm], hAlign='LEFT')
    tbl.setStyle(_tbl_style(hdr_col, colors.HexColor('#EBF5FB')))
    story.append(tbl)
    story.append(PageBreak())


def _invoice_section(story, styles, invoices, payments_map, sym, start, end, hdr_col, str_col):
    _section_header(story, styles, 2, 'Invoice List', hdr_col)

    inv_in_fy = [r for r in invoices
                 if start <= r.get('invoice_date', '') <= end]
    inv_in_fy = sorted(inv_in_fy, key=lambda r: r.get('invoice_date', ''))

    hdr = [Paragraph(h, styles['th']) for h in
           ['Date', 'Invoice #', 'Client', 'Total', 'Paid', 'Balance', 'Status']]
    rows = [hdr]
    total_t = total_p = total_b = 0.0
    for r in inv_in_fy:
        num    = r.get('invoice_number', '')
        total  = _f(r.get('total'))
        pmts   = payments_map.get(num, [])
        paid   = sum(_f(p.get('amount')) for p in pmts)
        bal    = total - paid
        status = r.get('invoice_status', '')
        if status in ('cancelled', 'void'):
            total = paid = bal = 0.0
        else:
            total_t += total
            total_p += paid
            total_b += bal
        rows.append([
            Paragraph(r.get('invoice_date', ''), styles['td']),
            Paragraph(num,                        styles['td']),
            Paragraph(r.get('client_name', ''),   styles['td']),
            Paragraph(_fmt(total, sym),           styles['tdr']),
            Paragraph(_fmt(paid,  sym),           styles['tdr']),
            Paragraph(_fmt(bal,   sym),           styles['tdr']),
            Paragraph(status,                     styles['td']),
        ])
    rows.append([
        Paragraph('', styles['td']),
        Paragraph('', styles['td']),
        Paragraph('<b>TOTALS</b>', styles['tdb']),
        Paragraph(_fmt(total_t, sym), styles['tdbr']),
        Paragraph(_fmt(total_p, sym), styles['tdbr']),
        Paragraph(_fmt(total_b, sym), styles['tdbr']),
        Paragraph('', styles['td']),
    ])
    tbl = Table(rows, colWidths=[22*mm, 22*mm, 48*mm, 22*mm, 22*mm, 22*mm, 20*mm],
                repeatRows=1)
    tbl.setStyle(_tbl_style(hdr_col, str_col))
    story.append(tbl)
    story.append(PageBreak())


def _ledger_section(story, styles, ledger, sym, start, end, hdr_col, str_col,
                    section_num, section_title, ledger_type):
    _section_header(story, styles, section_num, section_title, hdr_col)

    rows_in = sorted(
        [r for r in ledger
         if r.get('type') == ledger_type
         and start <= r.get('date', '') <= end
         and r.get('deleted', '') != '1'],
        key=lambda r: r.get('date', ''))

    # Group by category
    by_cat = {}
    for r in rows_in:
        cat = r.get('category', 'Uncategorised') or 'Uncategorised'
        by_cat.setdefault(cat, []).append(r)

    hdr = [Paragraph(h, styles['th']) for h in
           ['Date', 'Category', 'Description', 'Amount', 'Reference']]
    tbl_rows = [hdr]
    grand_total = 0.0

    for cat in sorted(by_cat):
        cat_rows = by_cat[cat]
        cat_total = sum(_f(r.get('amount')) for r in cat_rows)
        grand_total += cat_total
        for r in cat_rows:
            tbl_rows.append([
                Paragraph(r.get('date', ''),        styles['td']),
                Paragraph(cat,                       styles['td']),
                Paragraph(r.get('description', ''), styles['td']),
                Paragraph(_fmt(_f(r.get('amount')), sym), styles['tdr']),
                Paragraph(r.get('reference', ''),   styles['td']),
            ])
        tbl_rows.append([
            Paragraph('', styles['td']),
            Paragraph(f'<i>Subtotal — {cat}</i>', styles['td']),
            Paragraph('', styles['td']),
            Paragraph(_fmt(cat_total, sym), styles['tdbr']),
            Paragraph('', styles['td']),
        ])

    tbl_rows.append([
        Paragraph('', styles['td']),
        Paragraph('<b>TOTAL</b>', styles['tdb']),
        Paragraph('', styles['td']),
        Paragraph(_fmt(grand_total, sym), styles['tdbr']),
        Paragraph('', styles['td']),
    ])

    tbl = Table(tbl_rows, colWidths=[22*mm, 38*mm, 62*mm, 24*mm, 32*mm],
                repeatRows=1)
    tbl.setStyle(_tbl_style(hdr_col, str_col))
    story.append(tbl)
    story.append(PageBreak())


def _ato_section(story, styles, invoices, ledger, sym, start, end, hdr_col, str_col,
                 gst_rate, abn, biz):
    _section_header(story, styles, 5, 'ATO / BAS Summary', hdr_col)

    inv_fy  = [r for r in invoices if start <= r.get('invoice_date', '') <= end]
    led_fy  = [r for r in ledger   if start <= r.get('date', '') <= end
               and r.get('deleted', '') != '1']

    # GST collected
    gst_col = sum(_f(r.get('gst')) for r in inv_fy
                  if r.get('invoice_status', '') not in ('cancelled', 'void'))
    sales_excl = sum(_f(r.get('subtotal')) for r in inv_fy
                     if r.get('invoice_status', '') not in ('cancelled', 'void'))
    sales_incl = sales_excl + gst_col

    # GST paid (1/11 rule on expense ledger)
    expenses_incl = sum(_f(r.get('amount')) for r in led_fy if r.get('type') == 'out')
    gst_paid      = round(expenses_incl * gst_rate / (1 + gst_rate), 2)
    expenses_excl = round(expenses_incl - gst_paid, 2)

    net_gst = round(gst_col - gst_paid, 2)

    # Summary table
    summary_rows = [
        [Paragraph('<b>Item</b>', styles['th']),  Paragraph('<b>Amount</b>', styles['th'])],
        [Paragraph('Sales (excl. GST)',      styles['td']), Paragraph(_fmt(sales_excl,    sym), styles['tdr'])],
        [Paragraph('GST Collected (G1)',     styles['td']), Paragraph(_fmt(gst_col,       sym), styles['tdr'])],
        [Paragraph('Sales (incl. GST)',      styles['td']), Paragraph(_fmt(sales_incl,    sym), styles['tdr'])],
        [Paragraph('',                       styles['td']), Paragraph('',                       styles['tdr'])],
        [Paragraph('Expenses (incl. GST)',   styles['td']), Paragraph(_fmt(expenses_incl, sym), styles['tdr'])],
        [Paragraph('GST Credits (1B)',       styles['td']), Paragraph(_fmt(gst_paid,      sym), styles['tdr'])],
        [Paragraph('Expenses (excl. GST)',   styles['td']), Paragraph(_fmt(expenses_excl, sym), styles['tdr'])],
        [Paragraph('',                       styles['td']), Paragraph('',                       styles['tdr'])],
        [Paragraph('<b>Net GST Payable</b>', styles['tdb']), Paragraph(_fmt(net_gst,      sym), styles['tdbr'])],
    ]
    s_tbl = Table(summary_rows, colWidths=[110*mm, 40*mm], hAlign='LEFT')
    s_tbl.setStyle(_tbl_style(hdr_col, str_col))
    story.append(s_tbl)
    story.append(Spacer(1, 5*mm))

    # Per-invoice GST detail
    story.append(Paragraph('<b>Invoice GST Detail</b>', styles['h3']))
    inv_hdr = [Paragraph(h, styles['th']) for h in
               ['Date', 'Invoice #', 'Client', 'Excl. GST', 'GST', 'Total', 'Paid?']]
    inv_rows = [inv_hdr]
    for r in sorted(inv_fy, key=lambda x: x.get('invoice_date', '')):
        is_paid = r.get('invoice_status', '') == 'paid'
        inv_rows.append([
            Paragraph(r.get('invoice_date', ''),  styles['td']),
            Paragraph(r.get('invoice_number', ''), styles['td']),
            Paragraph(r.get('client_name', ''),   styles['td']),
            Paragraph(_fmt(_f(r.get('subtotal')), sym), styles['tdr']),
            Paragraph(_fmt(_f(r.get('gst')),      sym), styles['tdr']),
            Paragraph(_fmt(_f(r.get('total')),    sym), styles['tdr']),
            Paragraph('Yes' if is_paid else 'No', styles['td']),
        ])
    i_tbl = Table(inv_rows, colWidths=[22*mm, 22*mm, 46*mm, 22*mm, 20*mm, 22*mm, 14*mm],
                  repeatRows=1)
    i_tbl.setStyle(_tbl_style(hdr_col, str_col))
    story.append(i_tbl)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_accountant_pack(path, ds, settings: dict, fy: str = None):
    """
    Build the full accountant PDF report pack.

    Parameters
    ----------
    path     : str | Path
    ds       : DataStore instance
    settings : app settings dict
    fy       : financial year string e.g. '2025-2026'
               (defaults to current Australian FY)
    """
    settings  = settings or {}
    sym       = settings.get('currency_symbol', '$')
    biz       = settings.get('business_name', '')
    abn       = settings.get('business_abn', '')
    prepared  = settings.get('report_prepared_by', '')
    hdr_hex   = settings.get('report_header_colour', '#2C3E50')
    acc_hex   = settings.get('report_accent_colour',  '#2980B9')
    str_hex   = settings.get('report_stripe_colour',  '#EBF5FB')
    gst_rate  = float(settings.get('gst_rate', 0.10))

    try:
        hdr_col = colors.HexColor(hdr_hex)
    except Exception:
        hdr_col = colors.HexColor('#2C3E50')
    try:
        acc_col = colors.HexColor(acc_hex)
    except Exception:
        acc_col = colors.HexColor('#2980B9')
    try:
        str_col = colors.HexColor(str_hex)
    except Exception:
        str_col = colors.HexColor('#EBF5FB')

    # Determine FY
    now = datetime.now()
    if not fy:
        y = now.year
        fy = f'{y-1}-{y}' if now.month < 7 else f'{y}-{y+1}'
    start, end = _fy_dates(fy)

    styles = _make_styles(hdr_col, acc_col, str_col)

    # Load data
    invoices = ds.read_invoices()
    ledger   = ds.read_ledger()

    # Build payments map for invoice section
    payments_map = {}
    for inv in invoices:
        num = inv.get('invoice_number', '')
        if num:
            payments_map[num] = ds.payments_for_invoice(num)

    # Build story
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm,  bottomMargin=18*mm,
        title=f'Accountant Report Pack — {biz} — {fy}',
        author=prepared or biz,
    )

    story = []
    _cover(story, styles, biz, abn, fy, start, end, prepared, hdr_col)
    _pl_section(story, styles, invoices, ledger, sym, fy, start, end, hdr_col)
    _invoice_section(story, styles, invoices, payments_map, sym, start, end, hdr_col, str_col)
    _ledger_section(story, styles, ledger, sym, start, end, hdr_col, str_col,
                    3, 'Ledger — Income', 'in')
    _ledger_section(story, styles, ledger, sym, start, end, hdr_col, str_col,
                    4, 'Ledger — Expenses', 'out')
    _ato_section(story, styles, invoices, ledger, sym, start, end, hdr_col, str_col,
                 gst_rate, abn, biz)

    doc.build(story)
