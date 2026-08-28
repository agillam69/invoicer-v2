"""
app_theme.py
============
Centralised colour palette and ttk Style configuration for Invoice Generator.
Import this and call apply_theme(root) once at startup.
"""

import tkinter as tk
from tkinter import ttk

# ── Semantic palette ──────────────────────────────────────────────────────────
#   Row backgrounds for treeview status tags
ROW = {
    # Enrolment / course statuses
    'completed':              '#d4edda',   # solid green
    'enrolled':               '#cce5ff',   # solid blue
    'pending':                '#fff3cd',   # solid amber
    'confirmed':              '#cce5ff',   # alias for enrolled (courses)
    'scheduled':              '#ffcc80',   # orange (scheduled courses)
    'cancelled':              '#f8d7da',   # light red
    'cancelled & reallocated':'#ffeeba',   # amber-orange
    'withdrawn & not charged':'#e2e3e5',   # neutral grey
    'withdrawn & charged':    '#f8d7da',   # solid red-pink
    'withdrawn & reallocated':'#ffeeba',   # amber-orange
    'withdrawn & billed':     '#f8d7da',
    'cancelled & billed':     '#f8d7da',
    'no show':                '#f5c6cb',   # deeper red-pink
    'no show & billed':       '#f5c6cb',
    'deleted':                '#f5f5f5',   # faded grey
    # Ledger / budget
    'in':                     '#d4edda',
    'out':                    '#f8d7da',
    'topup':                  '#d4edda',
    'spend':                  '#f8d7da',
    # Invoice
    'paid':                   '#d4edda',
    'unpaid':                 '#fff3cd',
}

ROW_FG = {
    'deleted':  '#999999',
    'cancelled':'#721c24',
    'no show':  '#721c24',
    'out':      '#721c24',
    'spend':    '#721c24',
}

# ── Text / label colours ─────────────────────────────────────────────────────
LABEL_MUTED   = '#6c757d'
LABEL_SUCCESS = '#155724'
LABEL_DANGER  = '#721c24'
LABEL_INFO    = '#004085'
LABEL_DARK    = '#212529'

# ── Budget card colours ───────────────────────────────────────────────────────
CARD_BG          = '#f8f9fa'
CARD_BORDER      = '#dee2e6'
CARD_POSITIVE_FG = '#155724'
CARD_NEGATIVE_FG = '#721c24'
CARD_MUTED_FG    = '#495057'

# ── Sidebar (Reports) ─────────────────────────────────────────────────────────
SIDEBAR_BG        = '#f0f2f5'
SIDEBAR_SELECT_BG = '#0d6efd'
SIDEBAR_SELECT_FG = '#ffffff'
SIDEBAR_FG        = '#343a40'


def apply_theme(root: tk.Tk):
    """Apply global ttk Style tweaks."""
    style = ttk.Style(root)
    # Slightly larger default font for labels
    style.configure('TLabel',   font=('Segoe UI', 9))
    style.configure('TButton',  font=('Segoe UI', 9))
    style.configure('TEntry',   font=('Segoe UI', 9))
    style.configure('TCombobox', font=('Segoe UI', 9))
    style.configure('Treeview', font=('Segoe UI', 9), rowheight=22)
    style.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))
    style.configure('TNotebook.Tab', font=('Segoe UI', 9))


def configure_tags(tree: ttk.Treeview, tags=None):
    """Apply the standard palette tags to a Treeview.
    Pass an explicit list of tag names to configure only those."""
    wanted = tags or list(ROW.keys())
    for tag in wanted:
        kw = {'background': ROW[tag]}
        if tag in ROW_FG:
            kw['foreground'] = ROW_FG[tag]
        tree.tag_configure(tag, **kw)


# Columns that should NOT stretch (fixed-width content)
_NO_STRETCH_PATTERNS = {
    'id', 'student_id', 'enr_id', 'number',
    'date', 'course_date', 'cert_date', 'due_date', 'created_at',
    'type', 'status', 'enrolment_status',
    'amount', 'total', 'subtotal', 'gst', 'unit_price', 'cert_cost', 'total_billed',
    'qty', 'max_students', 'enrolled', 'invoices',
    'cert_issued', 'attendance', 'taxable',
    'phone', 'usi', 'role',
}


def configure_columns(tree: ttk.Treeview):
    """Set stretch and minwidth on all columns of a Treeview.

    Text-heavy columns (notes, description, name, email, etc.) get stretch=True
    so they expand with the window.  Narrow fixed-content columns get stretch=False
    to prevent them from growing unnecessarily.
    """
    for col in tree['columns']:
        current_width = tree.column(col, 'width')
        col_lower = col.lower()
        if col_lower in _NO_STRETCH_PATTERNS:
            tree.column(col, stretch=False, minwidth=max(30, min(current_width, 60)))
        else:
            tree.column(col, stretch=True, minwidth=max(50, current_width // 2))
