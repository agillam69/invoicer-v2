"""
client_statement.py
===================
Build a Client Statement of Account PDF using ReportLab.

Exports
-------
    build_client_statement_pdf(path, client_name, invoices, payments_by_invoice,
                                settings, as_at_date=None)

The PDF shows:
  • Header with business name, client name, and date
  • One row per invoice: date, invoice #, description/notes, total, paid, balance
  • Payment detail rows (indented) beneath each invoice
  • Running balance column
  • Footer totals: total invoiced, total paid, amount outstanding
"""

from pathlib import Path
from datetime import date as _date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


def _c(v) -> float:
    """Safe float conversion."""
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _fmt(v, sym='$') -> str:
    try:
        f = float(str(v).replace(',', '').strip())
        return f'{sym}{f:,.2f}'
    except (ValueError, TypeError):
        return str(v)


def build_client_statement_pdf(
    path,
    client_name: str,
    invoices: list,
    payments_by_invoice: dict,
    settings: dict = None,
    as_at_date: str = None,
):
    """
    Build the statement PDF.

    Parameters
    ----------
    path                : str | Path — output file path
    client_name         : str
    invoices            : list of invoice dicts (from DataStore.read_invoices)
                          filtered to this client, sorted by date
    payments_by_invoice : dict { invoice_number: [payment dicts, ...] }
    settings            : app settings dict (for business_name, currency_symbol etc.)
    as_at_date          : display string for the 'as at' date
    """
    settings  = settings or {}
    biz       = settings.get('business_name', '')
    sym       = settings.get('currency_symbol', '$')
    hdr_col   = settings.get('report_header_colour', '#2C3E50')
    acc_col   = settings.get('report_accent_colour',  '#2980B9')
    str_col   = settings.get('report_stripe_colour',  '#EBF5FB')
    as_at     = as_at_date or _date.today().strftime('%d/%m/%Y')

    try:
        hdr_rgb = colors.HexColor(hdr_col)
    except Exception:
        hdr_rgb = colors.HexColor('#2C3E50')
    try:
        acc_rgb = colors.HexColor(acc_col)
    except Exception:
        acc_rgb = colors.HexColor('#2980B9')
    try:
        str_rgb = colors.HexColor(str_col)
    except Exception:
        str_rgb = colors.HexColor('#EBF5FB')

    styles = getSampleStyleSheet()
    normal = styles['Normal']
    small  = ParagraphStyle('small',  parent=normal, fontSize=8)
    bold9  = ParagraphStyle('bold9',  parent=normal, fontSize=9,  fontName='Helvetica-Bold')
    h1     = ParagraphStyle('h1',     parent=normal, fontSize=16, fontName='Helvetica-Bold',
                             textColor=hdr_rgb)
    right8 = ParagraphStyle('right8', parent=normal, fontSize=8,  alignment=TA_RIGHT)
    right9 = ParagraphStyle('right9', parent=normal, fontSize=9,  fontName='Helvetica-Bold',
                             alignment=TA_RIGHT)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm,  bottomMargin=18*mm,
    )

    story = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    if biz:
        story.append(Paragraph(biz, h1))
        story.append(Spacer(1, 2*mm))

    story.append(Paragraph('STATEMENT OF ACCOUNT', ParagraphStyle(
        'stm', parent=normal, fontSize=13, fontName='Helvetica-Bold',
        textColor=acc_rgb)))
    story.append(Spacer(1, 3*mm))

    meta_data = [
        [Paragraph('<b>To:</b>', small),      Paragraph(client_name, bold9),
         Paragraph('<b>As at:</b>', small),    Paragraph(as_at, small)],
    ]
    meta_tbl = Table(meta_data, colWidths=[15*mm, 85*mm, 20*mm, 40*mm])
    meta_tbl.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=hdr_rgb))
    story.append(Spacer(1, 4*mm))

    # ------------------------------------------------------------------
    # Invoice table
    # ------------------------------------------------------------------
    col_hdrs = ['Date', 'Invoice #', 'Description', 'Total', 'Paid', 'Balance']
    col_w    = [22*mm, 22*mm, 65*mm, 22*mm, 22*mm, 22*mm]

    def _hdr_para(txt):
        return Paragraph(f'<b>{txt}</b>', ParagraphStyle(
            'th', parent=normal, fontSize=8, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=TA_CENTER))

    def _cell(txt, align=TA_LEFT, bold=False):
        st = ParagraphStyle('td', parent=normal, fontSize=8,
                            fontName='Helvetica-Bold' if bold else 'Helvetica',
                            alignment=align)
        return Paragraph(str(txt), st)

    def _rcell(txt, bold=False):
        return _cell(str(txt), TA_RIGHT, bold=bold)

    table_rows = [[_hdr_para(h) for h in col_hdrs]]
    row_styles = []

    running_balance = 0.0
    total_invoiced  = 0.0
    total_paid_all  = 0.0

    for idx, inv in enumerate(invoices):
        inv_num   = inv.get('invoice_number', '')
        inv_date  = inv.get('invoice_date', '')
        inv_notes = (inv.get('notes', '') or '')[:60]
        inv_total = _c(inv.get('total', 0))
        payments  = payments_by_invoice.get(inv_num, [])
        paid_sum  = sum(_c(p.get('amount', 0)) for p in payments)
        balance   = inv_total - paid_sum

        # cancelled invoices contribute $0 to running balance
        if inv.get('invoice_status', '') in ('cancelled', 'void'):
            inv_total = 0.0
            paid_sum  = 0.0
            balance   = 0.0

        running_balance += balance
        total_invoiced  += inv_total
        total_paid_all  += paid_sum

        data_row = [
            _cell(inv_date),
            _cell(inv_num),
            _cell(inv_notes),
            _rcell(_fmt(inv_total, sym)),
            _rcell(_fmt(paid_sum, sym)),
            _rcell(_fmt(running_balance, sym),
                   bold=(running_balance > 0.005)),
        ]
        table_rows.append(data_row)

        # Stripe every other invoice row (not header)
        row_idx = len(table_rows) - 1
        if idx % 2 == 1:
            row_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), str_rgb))

        # Payment detail sub-rows
        for pmt in payments:
            pmt_date = pmt.get('date', '')
            pmt_ref  = pmt.get('reference', '') or pmt.get('method', '')
            pmt_amt  = _c(pmt.get('amount', 0))
            pmt_style = ParagraphStyle(
                'pmt', parent=normal, fontSize=7.5,
                textColor=colors.HexColor('#1a7a1a'))
            pmt_r_style = ParagraphStyle(
                'pmt_r', parent=normal, fontSize=7.5,
                alignment=TA_RIGHT, textColor=colors.HexColor('#1a7a1a'))
            sub_row = [
                _cell(''),
                _cell(''),
                Paragraph(f'  ↳ Payment  {pmt_date}  {pmt_ref}', pmt_style),
                _cell(''),
                Paragraph(_fmt(pmt_amt, sym), pmt_r_style),
                _cell(''),
            ]
            table_rows.append(sub_row)

    # Totals footer row
    table_rows.append([
        _cell(''),
        _cell(''),
        _hdr_para('TOTALS'),
        _rcell(_fmt(total_invoiced, sym),  bold=True),
        _rcell(_fmt(total_paid_all, sym),  bold=True),
        _rcell(_fmt(running_balance, sym), bold=True),
    ])

    tbl = Table(table_rows, colWidths=col_w, repeatRows=1)

    base_style = [
        ('BACKGROUND',   (0, 0), (-1, 0), hdr_rgb),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.white]),
        ('BACKGROUND',   (0, -1), (-1, -1), hdr_rgb),
        ('FONTNAME',     (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, -1), (-1, -1), 8),
        ('GRID',         (0, 0), (-1, 0), 0.5, colors.white),
        ('LINEBELOW',    (0, -1), (-1, -1), 1, hdr_rgb),
        ('LINEBELOW',    (0, 0),  (-1, -1), 0.3, colors.HexColor('#dddddd')),
        ('VALIGN',       (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',   (0, 0),  (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0),  (-1, -1), 3),
        ('LEFTPADDING',  (0, 0),  (-1, -1), 4),
        ('RIGHTPADDING', (0, 0),  (-1, -1), 4),
    ]
    for rs in row_styles:
        base_style.append(rs)

    tbl.setStyle(TableStyle(base_style))
    story.append(tbl)

    # ------------------------------------------------------------------
    # Summary box
    # ------------------------------------------------------------------
    story.append(Spacer(1, 6*mm))
    outstanding = running_balance
    summary_data = [
        [Paragraph('<b>Total Invoiced</b>', small),  _rcell(_fmt(total_invoiced, sym),  bold=True)],
        [Paragraph('<b>Total Paid</b>',     small),  _rcell(_fmt(total_paid_all, sym),  bold=True)],
        [Paragraph('<b>Amount Outstanding</b>', ParagraphStyle(
            'out', parent=normal, fontSize=9, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#c0392b') if outstanding > 0.005 else colors.HexColor('#1a7a1a'))),
         _rcell(_fmt(outstanding, sym), bold=True)],
    ]
    sum_tbl = Table(summary_data, colWidths=[50*mm, 30*mm],
                    hAlign='RIGHT')
    sum_tbl.setStyle(TableStyle([
        ('LINEABOVE',    (0, 0), (-1, 0), 1, hdr_rgb),
        ('LINEBELOW',    (0, -1), (-1, -1), 1.5, hdr_rgb),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sum_tbl)

    doc.build(story)
