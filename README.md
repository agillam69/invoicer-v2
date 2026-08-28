# Invoicer V2

Invoicer V2 is a Windows desktop invoice, receipt, payment, client, service,
ledger, and reporting manager 

## Stack

- Python 3.12 and PySide6 for a native desktop interface.
- SQLite with SQLAlchemy 2.x and Alembic for a reliable local relational store.
- ReportLab with pypdf/pdfplumber for PDF generation and verification.
- Argon2id (`argon2-cffi`) for local password hashing.
- pytest, pytest-qt, Hypothesis, coverage, Ruff, and mypy for quality checks.

The database remains local. OneDrive is supported as a backup destination, not
as a multi-user live SQLite database.

## Architecture rule

PySide6 UI code calls application services. Application services use domain
rules and repositories. Persistence owns SQLAlchemy and SQLite. Calculation,
numbering, status, migration, and reconciliation logic must not live in UI
handlers.

## Storage layout

User data is separate from program files:

```text
InvoiceReceiptManager/
  data/business.sqlite3
  documents/invoices/YYYY/
  documents/receipts/YYYY/
  documents/credit-notes/YYYY/
  documents/attachments/
  exports/
  backups/
  logs/
```

## Setup

From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the application:

```powershell
python -m invoice_manager
```

Run tests and quality checks:

```powershell
python -m pytest
ruff check .
ruff format --check .
mypy src/invoice_manager
```

The Phase 1 foundation deliberately defers migration, invoice editing, PDF
templates, payment workflows, reports, backup/restore, and installer work to
later phases.
