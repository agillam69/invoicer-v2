# Invoice & Receipt Manager — Technical & User Reference

This document is the single reference for how the v2 application works,
how to use it, and how it is built. It covers user workflows, data layout,
architecture, domain rules, and build/test procedures.

For the original build specification and acceptance criteria, see
[`BUILD_SPEC.md`](BUILD_SPEC.md). For v1-to-v2 gap tracking, see
[`GAPS_2026-08-29.md`](GAPS_2026-08-29.md).

---

## 1. Overview

The **Invoice & Receipt Manager v2** is a single-user Windows desktop
application for a small Australian service business. It replaces the
previous v1 application by keeping the useful invoicing, payment, ledger,
and reporting features while removing the tightly-coupled student,
course, enrolment, and certificate modules.

### What it does

- Create professional tax invoices with line items, GST, and payment details.
- Track invoice status: draft, issued, part-paid, paid, overdue, cancelled,
  void.
- Record full or partial payments and generate receipt PDFs automatically.
- Reverse a payment if it was posted in error.
- Manage a catalogue of reusable products/services.
- Manage clients and print client statements of account.
- Record non-invoice income and business expenses in a general ledger.
- Mirror every payment into the ledger so income tracking stays consistent.
- Produce summary, invoice, ledger, GST, ageing, audit, and application-log
  reports with CSV/PDF export.
- Import legacy v1 CSV data (clients, services, invoices, ledger, settings,
  invoice PDFs).
- Back up and restore the entire data directory as a timestamped ZIP.
- Run scheduled or on-exit backups with configurable retention.

### What it does not do

- Student, course, enrolment, or certificate management.
- Bank-statement import and auto-match (explicitly skipped by the owner).
- Xero / MYOB accounting export (explicitly out of scope).
- Multi-user concurrency or cloud storage.

---

## 2. Installation & first run

### Running from source

Requires Python 3.14 and the project virtual environment.

```powershell
cd C:\Users\agill\OneDrive\Invoicer\invoicer-v2-temp
.venv\Scripts\python -m invoice_manager
```

### Running the built executable

```powershell
dist\InvoiceReceiptManager.exe
```

### First launch

1. The application creates `%LOCALAPPDATA%\InvoiceReceiptManager` for data,
   documents, exports, backups, and logs.
2. It prompts for a login. The first run creates the default `admin` user
   with password `admin`.
3. After login the main window opens with the left navigation rail.

### Changing where data lives

Open **Tools > Settings** and use the **Data directory** section. You can
browse to a folder or click **Use OneDrive** to select
`<OneDrive>\InvoiceReceiptManager`. A restart is required for the new
location to take effect.

---

## 3. Data and file layout

### Default storage

| Path | Purpose |
|---|---|
| `%LOCALAPPDATA%\InvoiceReceiptManager` | Application base directory |
| `...\config.json` | Runtime configuration, including `data_dir` override |
| `...\data\business.sqlite3` | SQLite database |
| `...\documents\` | Generated invoice, receipt, and statement PDFs |
| `...\exports\` | Exported CSV and report PDF files |
| `...\backups\` | Timestamped backup ZIPs |
| `...\logs\application.log` | Rotating diagnostic log (DEBUG and above) |
| `...\logs\error.log` | Rotating error-only log (ERROR and above) |

If a custom data directory is set, `config.json` remains in the base
directory but `business.sqlite3` and the `documents`, `exports`, `backups`,
and `logs` folders are created under the custom folder.

### The database

The SQLite database (`business.sqlite3`) uses SQLAlchemy ORM. It stores:

- `users` — login credentials (Argon2id hashes).
- `settings` — key/value application settings.
- `clients` — customer details, soft-delete flag.
- `service_items` — reusable catalogue entries, soft-delete flag.
- `invoices` and `invoice_items` — invoice headers and line items.
- `payments` — payments and receipts, with reversal support.
- `credit_notes` — credit note records (modelled, no UI yet).
- `ledger_entries` — income and expense entries, soft-delete flag.
- `audit_logs` — user-action audit trail.
- `documents` — metadata for attached files (by SHA-256 hash).
- `migration_issues` — records from v1 migration import problems.

### Money storage

All money amounts are stored as **integer cents**. Conversion uses
`ROUND_HALF_UP`. This avoids floating-point rounding errors. `$110.00`
is stored as `11000`.

---

## 4. User guide

### 4.1 Navigation

The main window has a left rail with these pages:

- **Dashboard** — unpaid total, overdue count/total, monthly income/expenses.
- **New Invoice** — opens the invoice editor.
- **Invoices** — list, search, cancel, void, regenerate PDF, open PDF.
- **Payments & Receipts** — record payments, view receipt PDFs, reverse payments.
- **Clients** — add, edit, delete, print statements.
- **Products & Services** — catalogue management.
- **Income & Expenses** — general ledger with add/edit/delete and CSV
  import/export.
- **Reports** — tabbed reports (Summary, Invoices, Ledger, GST, Ageing,
  Audit Log, Application Log).

The menu bar has **Tools** with **Settings**, **Backup now**, **Restore
from backup...**, and **Import / Migrate**.

### 4.2 Creating an invoice

1. Click **New Invoice**.
2. Select a client. If the client does not exist, add them first via the
   **Clients** page.
3. Add line items. You can choose a product/service from the catalogue
   to pre-fill description, unit price, and taxable flag.
4. Adjust quantity, discount, and taxable status as needed.
5. Click **Issue**. The invoice is assigned the next `INV-0001` style
   number and a PDF is generated.

An invoice remains editable while it is a **draft**. Once issued, the line
items cannot be changed from the invoice editor. Use **Cancel** or **Void**
for corrections, or use **Tools > Import / Migrate** or the manual invoice
dialog for historical adjustments.

### 4.3 Recording a payment

1. Go to **Payments & Receipts**.
2. Click **Record Payment**, select the invoice, enter amount, date,
   method, and reference.
3. A receipt PDF is generated with a `RCT-0001` style number.
4. The invoice status updates to `paid` or `part_paid` automatically.
5. An `Invoice Payment` income ledger entry is created automatically.

To reverse a payment, select it and click **Reverse**. Enter a reason. The
payment is marked reversed, the invoice status recalculates, and a reversal
ledger entry is posted.

### 4.4 Managing clients

- **Add/Edit**: select a client and click **Edit**.
- **Delete**: select a client and click **Delete**. This is a soft delete
  and will prompt for an optional note.
- **Statement**: select a client and click **Statement**. A PDF showing all
  invoices, payments, and outstanding balance is saved to the documents
  folder and opened.

### 4.5 Managing products and services

The **Products & Services** page maintains a catalogue of reusable items.
Each item has a description, unit price, unit, and taxable flag. When
adding an invoice line you can select from this catalogue to pre-fill
details.

### 4.6 Income and expenses (ledger)

The **Income & Expenses** page shows all ledger entries. Use **Add** to
create a new entry. The category dropdown changes depending on whether the
entry is **Income** or **Expense**.

- **Edit**: select an entry and click **Edit**.
- **Delete**: select an entry, click **Delete**, and optionally enter a
  reason. Deleted entries are soft-deleted and no longer appear in reports.
- **Import CSV / Export CSV**: import or export the ledger in CSV format.

Payment recording creates ledger entries automatically, so the ledger stays
in sync with invoiced income.

### 4.7 Reports

The **Reports** page has several tabs:

- **Summary** — invoice, ledger, and GST totals. Export CSV or PDF.
- **Invoices** — filterable grid by status, client, and date range.
  Export CSV.
- **Ledger** — filterable grid by type, category, and date range.
  Export CSV.
- **GST** — GST collected from invoices and estimated GST credits from
  expenses. Uses the configured `gst_rate`.
- **Ageing** — outstanding balances grouped by days overdue.
- **Audit Log** — searchable audit trail. Export CSV.
- **Application Log** — filtered view of `application.log`. Export text.

### 4.8 Settings

Open **Tools > Settings**. Fields are saved to the database `settings`
table (except the data directory, which is saved to `config.json`).

Key settings:

- **Business** — name, address, ABN, phone, email, currency symbol.
- **Bank** — name, BSB, account number, account name (printed on invoices).
- **GST rate / Payment terms** — default rate and due-date offset in days.
- **Next invoice / receipt number** — manual override of numbering.
- **Reports & PDF** — header colour, accent colour, stripe colour, footer
  text, and PDF save mode (`Auto` or `Prompt`).
- **Backup** — enable scheduled backups, frequency in hours, keep count,
  backup on exit, and backup folder.
- **Data directory** — change where the database, documents, exports,
  backups, and logs are stored.

### 4.9 Backup and restore

- **Manual backup**: **Tools > Backup now**. Creates a timestamped ZIP
  containing `backup_manifest.json` and the `data/` tree.
- **Scheduled backups**: enable in Settings. A background check runs every
  15 minutes. Backups are created when the configured interval has passed.
- **Backup on exit**: enable in Settings. A backup is attempted when the
  main window closes.
- **Retention**: the oldest backups beyond the **Keep count** are pruned.
- **Restore**: **Tools > Restore from backup...** selects a ZIP. A safety
  copy of the current data is created before the restore proceeds. The
  manifest is validated and backups from v1 are rejected.

### 4.10 Migrating from v1

1. Place the v1 CSV files (`clients.csv`, `service_items.csv`,
   `invoices.csv`, `ledger.csv`) and `settings.json` in a folder.
2. Optionally include an `invoices/` subfolder with old invoice PDFs.
3. Choose **Tools > Import / Migrate** and select the source folder.
4. The wizard imports recognised files, skips student/course ledger
categories (`Certification Fee`, `Cert Budget`, `Invoice Payment`),
   flags unknown clients and invalid invoice numbers, and updates the next
   invoice/receipt numbers from the highest imported sequence.
5. Review migration issues in the dialog.

---

## 5. Technical architecture

### 5.1 Layered package layout

```text
src/invoice_manager/
├── app.py                 # Entry point: config, login, main window
├── __main__.py            # Console entry point
├── domain/                # Pure business rules (no UI or DB)
│   ├── invoices.py        # Line-item / GST / total calculations
│   ├── money.py           # Cents conversion and Money value object
│   ├── numbering.py       # Sequential INV/RCT/CN numbering
│   ├── statuses.py        # Invoice status derivation
│   └── validation.py      # Date parsing and helpers
├── application/           # Application services / use-cases
│   ├── audit_service.py
│   ├── auth_service.py
│   ├── backup_service.py
│   ├── invoice_service.py
│   ├── ledger_service.py
│   ├── migration_service.py
│   └── payment_service.py
├── persistence/           # SQLAlchemy ORM, database, repositories
│   ├── database.py
│   ├── models.py
│   └── repositories.py
├── infrastructure/        # Cross-cutting concerns
│   ├── audit.py
│   ├── config.py
│   ├── file_store.py
│   ├── instance_lock.py
│   └── logging_setup.py
├── ui/                    # PySide6 widgets and dialogs
│   ├── app_context.py
│   ├── main_window.py
│   ├── dashboard_page.py
│   ├── invoice_editor.py
│   ├── invoice_list.py
│   ├── payments_page.py
│   ├── clients_page.py
│   ├── service_items_page.py
│   ├── ledger_page.py
│   ├── reports_page.py
│   ├── settings_dialog.py
│   ├── migration_wizard.py
│   └── ...
└── documents/             # ReportLab PDF builders
    ├── client_statement_pdf.py
    ├── invoice_pdf.py
    └── receipt_pdf.py
```

### 5.2 `AppContext`

`AppContext` is constructed once at login and shared with every UI page.
It wires together:

- `AppConfig` and file store
- SQLAlchemy `session`
- repositories
- `AuditService`
- `InvoiceService`, `PaymentService`, `LedgerService`

This keeps the UI pages thin and ensures all business operations share the
same transaction session.

### 5.3 Domain rules

#### Money

All stored amounts are `int` cents. The `Money` class and `to_cents()`
helper parse strings that may contain `$`, commas, or `Decimal` values and
round using `ROUND_HALF_UP`.

#### Invoice totals

Each line item computes:

```text
gross      = quantity * unit_price_cents
taxable_base = max(0, gross - discount_cents)
gst        = round(taxable_base * gst_rate)  # if taxable
total      = taxable_base + gst
```

Invoice subtotal, GST, and total are the sums of line item values.

#### Status derivation

Status is derived from financial facts, not stored independently. The order
of precedence is:

1. `void`
2. `cancelled`
3. `paid` / `credited` (balance <= 0)
4. `part_paid` (0 < balance < total)
5. `overdue` (due date in the past and still outstanding)
6. `issued`
7. `draft`

#### Numbering

`NumberingService` reserves sequential numbers with fixed prefixes:

- Invoices: `INV-0001`
- Receipts: `RCT-0001`
- Credit notes: `CN-0001`

The next values are persisted in the `settings` table. `parse_number()`
can also parse manual numbers like `42` or `INV-0042`.

### 5.4 Persistence

`Database` creates the SQLite engine and schema. `DeclarativeBase` models
are defined in `persistence/models.py`. Repositories in
`persistence/repositories.py` provide typed access for each entity.

Soft deletion is implemented via `is_deleted` flags on `Client`,
`ServiceItem`, and `LedgerEntry`. Most list queries filter with
`is_deleted.is_(False)`.

### 5.5 Application services

- `InvoiceService` — create draft, add/remove lines, issue, cancel, void,
  manual invoice entry, recalculate status, regenerate PDF.
- `PaymentService` — record payment, generate receipt, reverse payment,
  mirror payments to the ledger via `LedgerService`.
- `LedgerService` — add, update, delete (soft) ledger entries.
- `BackupService` — create and restore ZIP backups, prune old archives,
  read backup settings.
- `MigrationService` — import v1 CSVs and PDFs, flag issues.
- `AuthService` — Argon2id password hashing and default admin creation.
- `AuditService` — structured audit logging.

### 5.6 PDF generation

PDFs are built with ReportLab:

- `generate_invoice_pdf()` — A4 invoice with business header, client, line
  items, totals, GST, payment instructions, thank-you note.
- `generate_receipt_pdf()` — receipt for a payment.
- `generate_client_statement_pdf()` — statement of account for a client.
- `generate_report_pdf()` — simple text report for the Summary tab.

PDF save behaviour is controlled by `pdf_save_mode`:

- `Auto` — save to the configured documents directory.
- `Prompt` — ask the user for a location.

### 5.7 Audit and logging

`AuditService` writes to the `audit_logs` table with `timestamp`, `user`,
`action`, `table_name`, `record_id`, and JSON `detail`. Important actions
(invoice issue, payment, reversal, delete, backup, restore, report export)
are logged.

`setup_logging()` configures rotating files for `logs/application.log`
(DEBUG and above) and `logs/error.log` (ERROR and above), each limited to
5 MB with 10 backups, plus console output. Frozen builds also write a log
beside the executable when that folder is writable. The Reports >
Application Log tab reads `application.log`.

---

## 6. Settings reference

Settings are stored in the SQLite `settings` table unless noted.

| Key | Type | Used by | Default |
|---|---|---|---|
| `business_name` | string | Invoice PDF, reports | `""` |
| `business_address` | string | Invoice PDF | `""` |
| `business_abn` | string | Invoice PDF | `""` |
| `business_phone` | string | Invoice PDF, reports | `""` |
| `business_email` | string | Invoice PDF | `""` |
| `currency_symbol` | string | Money formatting | `"$"` |
| `bank_name` | string | Invoice PDF | `""` |
| `bank_bsb` | string | Invoice PDF | `""` |
| `bank_account` | string | Invoice PDF | `""` |
| `bank_account_name` | string | Invoice PDF | `""` |
| `thank_you_note` | string | Invoice PDF | `""` |
| `gst_rate` | decimal | Line GST, reports | `"0.0"` |
| `payment_terms_days` | integer | Due date | `7` |
| `next_invoice_number` | integer | NumberingService | `1` |
| `next_receipt_number` | integer | NumberingService | `1` |
| `report_header_colour` | hex string | Reports PDF | `"#2C3E50"` |
| `report_accent_colour` | hex string | Reports PDF | `"#2980B9"` |
| `report_stripe_colour` | hex string | Reports PDF | `"#EBF5FB"` |
| `report_footer` | string | Reports PDF | `""` |
| `pdf_save_mode` | `Auto`/`Prompt` | PDF dialogs | `"Auto"` |
| `backup_enabled` | `1`/`0` | Backup scheduler | `"0"` |
| `backup_frequency_hours` | integer | Backup scheduler | `24` |
| `backup_keep` | integer | Backup pruning | `30` |
| `backup_on_exit` | `1`/`0` | Backup on close | `"0"` |
| `backup_folder` | path | Backup location | `""` |

The data directory override is stored in `config.json` under the key
`data_dir`.

---

## 7. Backup internals

A backup is a ZIP archive with this structure:

```text
invoice_manager_backup_YYYYMMDD_HHMMSS_uuuuuu.zip
├── backup_manifest.json
└── data/
    ├── business.sqlite3
    ├── documents/...
    └── exports/...
```

`backup_manifest.json` contains:

```json
{
  "created_at": "2026-08-29T06:40:19.123456",
  "version": "2.0",
  "data_dir": "C:/.../InvoiceReceiptManager/data"
}
```

The restore process:

1. Validate the manifest exists and `version` is `2.0`.
2. Create a safety copy of the current data directory.
3. Extract the `data/` tree into the configured data directory.
4. Re-open the database on next launch (restart is recommended after restore).

Backup naming includes microseconds to avoid collisions when multiple
backups run in the same second.

---

## 8. Migration internals

`MigrationService` imports from a source directory:

| File | Imported |
|---|---|
| `settings.json` | All string key/value settings |
| `clients.csv` | `name`, `contact_name`, `phone`, `email`, `address` |
| `service_items.csv` | `description`, `unit_price`, `taxable` |
| `invoices.csv` | Header fields; one synthetic line item per invoice |
| `ledger.csv` | Non-deleted rows with supported categories |
| `invoices/invoice_<number>.pdf` | Imported into document store if present |

Ledger rows are skipped if:

- `deleted` is truthy.
- `category` is empty.
- `category` is in the excluded set (`Invoice Payment`, `Certification Fee`,
  `Cert Budget`).

Invoice rows are skipped if:

- `invoice_number` cannot be parsed.
- `invoice_number` is the placeholder form `0001-1` (used for error rows).
- `client_name` does not match an imported client.
- `invoice_date` is missing.

Migration issues are saved to `migration_issues` and shown in the wizard.

---

## 9. Testing

The test suite uses `pytest`, `pytest-qt`, and `pdfplumber`.

```powershell
.venv\Scripts\ruff check src tests
.venv\Scripts\ruff format --check src tests
.venv\Scripts\mypy -p invoice_manager
.venv\Scripts\pytest
```

Current result: **80 tests passed**.

Test groups:

- `tests/domain/` — pure business rules (money, statuses, numbering, etc.)
- `tests/integration/` — services with real SQLite database
- `tests/migration/` — v1 CSV migration, including live v1 data smoke test
- `tests/pdf/` — PDF output verification with `pdfplumber`
- `tests/gui/` — login and main window smoke tests

---

## 10. Build and packaging

### PyInstaller executable

```powershell
.venv\Scripts\python -m PyInstaller InvoiceReceiptManager.spec --noconfirm
```

Output: `dist\InvoiceReceiptManager.exe` (~63 MB).

### Inno Setup installer

The installer script is `installer\InvoiceReceiptManager.iss`. Build it
with `ISCC` when Inno Setup is available:

```powershell
ISCC installer\InvoiceReceiptManager.iss
```

---

## 11. Remote database rollout plan

The supported production database remains the local SQLite file at
`data\business.sqlite3`. Remote MySQL/MariaDB support is staged in the data
access layer but is intentionally disabled in this release. The application
always selects SQLite, and Settings displays remote database support as a
planned feature.

Before enabling MySQL in a future release:

1. Add and package a pinned PyMySQL dependency.
2. Run the complete integration suite against supported MySQL and MariaDB
   versions, including concurrent invoice numbering and transaction rollback.
3. Add TLS/CA configuration and require encrypted connections for hosted
   databases.
4. Add a pre-login recovery/configuration screen so an invalid remote
   connection cannot prevent access to Settings.
5. Provide a guided SQLite-to-MySQL data migration with record-count and
   financial-total verification.
6. Confirm server backup/restore procedures and test CSV application exports.
7. Enable `AppConfig.REMOTE_DATABASE_ENABLED` only after those checks pass.

Remote passwords must never be written to `config.json`; the staged design
reads them from a named environment variable.

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Login fails | `admin` user has been changed or database removed | Delete or rename `business.sqlite3` and restart to recreate the default admin |
| PDF does not open | Default PDF viewer issue | Open the documents folder manually from **Tools > Settings** |
| Backup not running | `backup_enabled` is off or `backup_folder` is invalid | Check Settings > Backup |
| Migration missing clients | Unknown `client_name` in `invoices.csv` | Ensure `clients.csv` is imported first and names match exactly |
| GST looks wrong | `gst_rate` not set | Set **GST rate** in Tools > Settings (e.g. `0.10`) |
| Application won't start | Corrupt `config.json` | Rename `%LOCALAPPDATA%\InvoiceReceiptManager\config.json` and restart |

---

## 13. Glossary

- **Soft delete** — records are flagged `is_deleted = True` instead of
  being physically removed, preserving history and referential integrity.
- **Sequence number** — the integer part of a document number (`1` in
  `INV-0001`). Stored separately from the prefix.
- **Balance** — `invoice.total_cents - sum(non-reversed payment amounts)`.
- **Cents** — all monetary amounts are stored as integer cents (`$1.23` =
  `123`).
- **Audit log** — a tamper-evident record of business actions performed by
  the current user.
