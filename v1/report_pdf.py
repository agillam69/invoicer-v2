"""
report_pdf.py
=============
ReportLab-based PDF generator for the Reports tab.

Public API
----------
build_report_pdf(path, title, columns, rows, summary_lines=None,
                 notes='', prepared_by='', footer='', org='',
                 header_colour='#2C3E50', accent_colour='#2980B9',
                 stripe_colour='#EBF5FB')

    path            : str or Path — destination file
    title           : str         — report title shown in header
    columns         : list[str]   — column heading labels (display names)
    rows            : list[list]  — data rows (each a list of cell strings)
    summary_lines   : list[str]   — optional lines printed above the table
    notes           : str         — free-text notes block printed below table
    prepared_by     : str         — printed in header
    footer          : str         — footer text on every page
    org             : str         — organisation / business name in header
    header_colour   : hex str     — top banner background
    accent_colour   : hex str     — column header row background
    stripe_colour   : hex str     — alternating data row tint
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, KeepTogether,
)


# ---------------------------------------------------------------------------
# Colour helper
# ---------------------------------------------------------------------------
def _hex(h: str):
    """Convert a #RRGGBB hex string to a ReportLab HexColor."""
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return colors.Color(r / 255, g / 255, b / 255)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_report_pdf(
    path,
    title: str,
    columns: list,
    rows: list,
    summary_lines: list = None,
    notes: str = '',
    prepared_by: str = '',
    footer: str = '',
    org: str = '',
    header_colour: str = '#2C3E50',
    accent_colour: str  = '#2980B9',
    stripe_colour: str  = '#EBF5FB',
):
    path = str(path)
    now  = datetime.now().strftime('%d %b %Y  %H:%M')

    # Use landscape if many columns
    pagesize = landscape(A4) if len(columns) > 7 else A4
    doc = SimpleDocTemplate(
        path,
        pagesize=pagesize,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=20 * mm,  bottomMargin=20 * mm,
    )

    styles   = getSampleStyleSheet()
    hdr_col  = _hex(header_colour)
    acc_col  = _hex(accent_colour)
    str_col  = _hex(stripe_colour)
    white    = colors.white
    near_blk = colors.Color(0.15, 0.15, 0.15)

    title_style = ParagraphStyle('RptTitle', parent=styles['Heading1'],
                                 fontSize=16, textColor=white,
                                 spaceAfter=2, leading=20)
    sub_style   = ParagraphStyle('RptSub',   parent=styles['Normal'],
                                 fontSize=8,  textColor=colors.Color(0.8, 0.85, 0.9),
                                 spaceAfter=0)
    body_style  = ParagraphStyle('RptBody',  parent=styles['Normal'],
                                 fontSize=9,  textColor=near_blk, spaceAfter=4)
    notes_style = ParagraphStyle('RptNotes', parent=styles['Normal'],
                                 fontSize=9,  textColor=near_blk,
                                 borderPad=4, borderWidth=0.5,
                                 borderColor=colors.Color(0.7, 0.7, 0.7),
                                 backColor=colors.Color(0.97, 0.97, 0.97))
    col_style   = ParagraphStyle('ColHdr',   parent=styles['Normal'],
                                 fontSize=8,  textColor=white,
                                 fontName='Helvetica-Bold')
    cell_style  = ParagraphStyle('Cell',     parent=styles['Normal'],
                                 fontSize=8,  textColor=near_blk,
                                 wordWrap='CJK')

    story = []

    # ---- Page-width banner ----
    page_w = pagesize[0] - 30 * mm
    banner_data = [[
        Paragraph(title, title_style),
        Paragraph(
            f'{org}<br/>'
            f'Prepared: {now}'
            + (f'  |  By: {prepared_by}' if prepared_by else ''),
            sub_style)
    ]]
    banner = Table(banner_data, colWidths=[page_w * 0.6, page_w * 0.4])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), hdr_col),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('RIGHTPADDING', (1, 0), (1, 0), 14),
    ]))
    story.append(banner)
    story.append(Spacer(1, 6 * mm))

    # ---- Summary lines ----
    if summary_lines:
        for line in summary_lines:
            story.append(Paragraph(line, body_style))
        story.append(Spacer(1, 4 * mm))

    # ---- Table ----
    if rows:
        # Auto-distribute column widths
        n_cols   = len(columns)
        col_w    = page_w / n_cols

        header_row = [Paragraph(c, col_style) for c in columns]
        table_data = [header_row]
        for row in rows:
            table_data.append([
                Paragraph(str(v) if v is not None else '', cell_style)
                for v in row
            ])

        tbl = Table(table_data, colWidths=[col_w] * n_cols, repeatRows=1)
        n_data = len(rows)

        tbl_style = [
            ('BACKGROUND', (0, 0), (-1, 0), acc_col),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 8),
            ('TEXTCOLOR',  (0, 0), (-1, 0), white),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.Color(0.75, 0.75, 0.75)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [white, str_col]),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ]
        tbl.setStyle(TableStyle(tbl_style))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f'{n_data} row(s)', body_style))
    else:
        story.append(Paragraph('No data to display.', body_style))

    # ---- Notes block ----
    if notes and notes.strip():
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width='100%', thickness=0.5,
                                color=colors.Color(0.75, 0.75, 0.75)))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph('<b>Notes</b>', body_style))
        story.append(Paragraph(notes.replace('\n', '<br/>'), notes_style))

    # ---- Footer on every page ----
    footer_text = footer or ''

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.Color(0.5, 0.5, 0.5))
        canvas.drawString(15 * mm, 10 * mm, footer_text)
        canvas.drawRightString(
            pagesize[0] - 15 * mm, 10 * mm,
            f'Page {doc.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
