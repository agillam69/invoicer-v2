# Invoice Generator (v1 trimmed)

A desktop GUI application for invoicing, payment tracking, client management,
ledger, financial reporting, and automated data backups.

> This copy of the v1.49 source has the student/course/enrolment/certificate
> management features removed. Those features now live in the separate
> Student Tracker 2 project. The documentation below still mentions some of
> those features and will be refreshed in a later pass.

Built with **Python 3 + Tkinter** (GUI), **ReportLab** (PDF), and **python-docx** (Word certificates).  
No database required — all data is stored in plain CSV and JSON files you can open in any spreadsheet app.

> **Current version: 1.49** — 649 automated tests passing.

---

## Features at a glance

### Invoicing
- Auto-incrementing invoice numbers with persistent counter
- Client database with contact details and auto-fill
- Service catalogue for one-click line-item entry
- Per-item GST (configurable rate) with live subtotal / GST / total
- Professional PDF output — business header, payment details, thank-you note
- Invoice History with **Paid / Unpaid / Cancelled / Void** status, colour-coded rows, and payment recording
- **Cancel Invoice** — mark an invoice as cancelled while keeping the record for audit
- **Reissue Invoice** — regenerate the PDF for an existing invoice under the same number
- **Link PDF** — point an invoice (especially older ones) at an external PDF/document instead of the default file
- **Reveal Invoice Folder** — open the invoice PDF folder in Explorer from both Invoice History and Create Invoice
- **Record Missing Invoice** — enter a past invoice (e.g. issued as Word/email) directly into the CSV without generating a PDF; auto-suggests next unused number; duplicate check

### Student & Course Management
- Student register with USI, work group, manager, emergency contact fields
- **Soft delete & restore** — deleted students/courses/enrolments are hidden but never lost; toggle "Show Deleted" to view or restore them
- **Student profile panel** — click any student to see name, email, phone, USI, work group, manager, emergency contact, enrolment count, completed count, and certs issued in a summary bar
- **View Enrolments** — open a read-only dialog showing every enrolment for the selected student
- **Manual Merge** — pick any two student records side-by-side, choose which field values to keep, re-point all enrolments, then permanently delete the duplicate
- **Auto-Merge Duplicates** — automatically find and merge records that share the same email or full name
- Course management — schedule courses, assign trainers, set cert cost per course
- Enrolment system with full status tracking and budget impact rules
- Auto-budget spend — cert cost is deducted from the pool automatically on enrolment; reversed on delete or cancellation
- Word (.docx) course completion certificates — single or batch, signed by Training Manager
- Booking Report — multi-course selection, status filtering, budget draw estimate, CSV export

### Enrolment Status System
| Status | Budget impact | On cert sign-off? |
|--------|--------------|-------------------|
| pending | No change | No |
| enrolled | Deducts cert cost | Yes |
| completed | Deducts cert cost | Yes |
| cancelled & reallocated | No change (free place) | No |
| withdrawn & reallocated | No change (free place) | No |
| withdrawn & charged | No change | No |
| withdrawn & not charged | No change | No |
| cancelled & billed | Billed externally | No |
| withdrawn & billed | Billed externally | No |
| no show | Deducts cert cost | Yes |
| no show & billed | Billed externally | No |

### Smart Clipboard (all tables)
- **Right-click** any list/table → Copy Row(s), Copy Cell, Copy All, Select All
- `Ctrl+C` copy selected · `Ctrl+A` select all · `Ctrl+Shift+C` copy all rows
- **Paste from clipboard** — tab-separated (Excel) or CSV, auto-detected
- **Smart name splitting** — handles `Firstname Lastname`, `Last, First`, `name` header, `full_name` header, no-header fallback
- Import from CSV file buttons on Students, Enrolments, and Ledger tabs
- Export to CSV buttons on every tab

### Financial
- Ledger tab — record money in/out (non-invoice transactions) with categories
- Certificate budget tracking — top-ups and per-enrolment deductions with automatic reversal on status change
- Reports tab — P&L summary, invoice ageing, student summary, structured audit log, app log viewer

### Logging & Audit
- **Structured audit log** (`audit.csv`) — every create/update/delete records action, table, record ID, detail, and timestamp
- **Application log** (`invoicer.log`) — rotating log (5 MB × 10 files); structured startup banner (Python version, OS, PID, paths); captures all events, errors, and unhandled exceptions
- **Dev console** — in source-run mode the log also streams to stdout for easy debugging; suppressed in the frozen EXE
- **`log_event()`** — structured business-event entries: `[INVOICE] created | #42 Acme $550.00`
- **`log_summary()`** — structured import/export summaries: `[SUMMARY] import_xlsx | courses_created=3 enrolments_created=17 skipped=2`
- **Reports → App Log** tab — colour-coded live viewer with level filter (All/DEBUG/INFO/WARNING/ERROR/CRITICAL), keyword search, and export

### Cloud / OneDrive
- Data folder is fully configurable — point it at any OneDrive subfolder
- **Settings → Config** auto-detects your OneDrive path and offers one-click "Use OneDrive folder"
- **Move existing data there…** — copies all CSV/PDF files to the new folder then switches; originals kept until you delete them
- Once pointing at OneDrive the files sync automatically across devices

### Automated Backups
- **Settings → Backup tab** — enable scheduled backups with configurable frequency (hourly to daily), destination folder, and retention count
- Backups run silently in a background daemon thread — never interrupts the UI
- Each backup is a timestamped zip (`invoicer_backup_YYYYMMDD_HHMMSS.zip`) containing all CSVs, JSON, PDFs, and logs
- **Keep last N copies** — older backups pruned automatically
- **Backup on exit** — optional final backup every time the app closes
- **Tools → Backup Now** — immediate manual backup with folder confirmation
- **Settings → Backup → Refresh list** — shows last 8 backups with size and timestamp

### Security & Users
- **Login screen at startup** — every launch requires a username and password
- Default account: **`admin` / `Admin`** (change or add users any time)
- **Users menu → Manage Users** — add, edit passwords, and delete users (no password complexity rules, no RBAC)
- Users stored in `users.csv`; current user shown in the status bar

### Windows Integration & UX
- **Settings → Startup tab** — toggle "Start on Windows startup (Delayed Run)"; the entry appears in Windows **Settings → Apps → Startup** and can be disabled from there or in-app
- **Status bar** — live system date/time, current user, and the program's install location in the bottom corner
- **Auto-refresh** — all tabs reload periodically so externally-synced changes appear without restarting
- **Course completion prompts** — on load, you're asked whether to mark past-dated courses as completed
- **Certificate prompt** — when a course is set to *completed*, you're asked whether to mark all certificates as issued
- **Course status colours** — *scheduled* shows orange, *pending* amber, *cancelled* light red

### Date Handling
- All date fields show a **calendar picker** — click to choose, or type in any common format
- **Smart parser** accepts dd/mm/yyyy, dd-mm-yyyy, d/m/yy, yyyy-mm-dd, 25 Jun 2026, 25Jun2026, and more
- All dates displayed as **dd/mm/yyyy** throughout the UI (non-American format)
- Dates stored internally as yyyy-mm-dd in CSV; converted automatically on load/save

### Version & About
- **Help → About Invoice Generator…** — shows version, data format, PDF engine, Python version
- Window title bar shows current version (e.g. `Invoice Generator v1.9`)
- `VERSION` file beside the EXE controls the displayed version

### Migration
- **Tools → Migrate from V1.8 folder/zip…** — import a plain folder or `.zip` from V1.8 or earlier; all schemas are upgraded automatically
- `migrate_all()` reports exactly which columns were added to which files; idempotent (safe to run repeatedly)

---

## Requirements

| Dependency | Install |
|------------|---------|
| Python 3.8+ | [python.org](https://python.org) |
| ReportLab | `pip install reportlab` |
| python-docx | `pip install python-docx` |
| openpyxl | `pip install openpyxl` |

All other imports (`tkinter`, `csv`, `json`, `os`, `pathlib`, `datetime`, `zipfile`) are standard-library.

---

## Quick Start

```bash
pip install reportlab python-docx openpyxl
python invoice_gui.py
```

On first run the app creates these files beside the script/EXE (or in the configured data folder):

| Path | Purpose |
|------|---------|
| `settings.json` | All configurable settings |
| `config.json` | Data-folder location (written beside the EXE; points to data folder) |
| `clients.csv` | Saved client records |
| `service_items.csv` | Service catalogue |
| `invoices.csv` | Invoice log (inc. payment status) |
| `invoices/` | Generated PDF invoices |
| `ledger.csv` | Non-invoice transactions |
| `students.csv` | Student register |
| `cert_budgets.csv` | Certificate budget pool entries |
| `courses.csv` | Course schedule |
| `enrolments.csv` | Course enrolments with status |
| `course_logs.csv` | Per-course log entries |
| `audit.csv` | Structured audit trail (table + record_id + action) |
| `invoicer.log` | Rotating application log (5 MB × 10 backup files) |
| `course_types.csv` | Course type catalogue (name, default cert cost, pool) |
| `custom_reports.json` | Saved custom report definitions |
| `backups/` | Auto-backup zip files (if backup folder not overridden) |

---

## Application Layout

The window has a **Tools** menu and these top-level tabs:

| Tab | Sub-tabs / contents |
|-----|---------------------|
| Create Invoice | Build and save invoices |
| Invoice History | Review, pay, and export past invoices |
| Clients | Client summary with invoice stats |
| Ledger | Non-invoice money in/out |
| Students | Student Register · Certificate Budget |
| Courses | Course List · Course Detail · Booking Report · Course Reports |
| Reports | Business Summary · Invoice Report · Ledger Report · Students Report · Cert Budget · ATO Tax Report · Custom Report · Audit Log · App Log |

---

## Tab: Create Invoice

### Invoice Details panel

| Field | Notes |
|-------|-------|
| Invoice # | Auto-incremented, read-only |
| Invoice date | Defaults to today (DD/MM/YYYY, editable) |
| Due date | Defaults to today + payment terms days |
| Select client | Dropdown — auto-fills name & address |
| Client name | Required |
| Client address | Optional multi-line |
| Notes | Optional — printed on the PDF |

### Line Items

| Field | Notes |
|-------|-------|
| Service | Catalogue dropdown — auto-fills description, price, taxable flag |
| Description | Required |
| Qty | Positive number |
| Unit price | Non-negative |
| Taxable | GST added at configured rate when ticked |

- **Add Item / Update Item / Cancel Edit** — inline editing
- **Double-click** a row to edit it
- **Remove Selected** — deletes the highlighted row

### Action buttons

| Button | Action |
|--------|--------|
| Save Invoice | Validate → CSV → PDF → advance counter → clear form |
| Clear | Reset without saving |

---

## Tab: Invoice History

Displays all invoices newest-first.

| Column | Notes |
|--------|-------|
| Invoice # | |
| Date / Due Date | |
| Client | |
| Total | Currency-prefixed |
| Status | **Paid** (green) / **Unpaid** (amber) |

- **Open PDF** — open in system viewer (disabled for invoices with no PDF file)
- **Record Payment** — mark paid, set date, add note
- **Record Missing Invoice…** — add a past invoice that was issued outside the app (Word, email, etc.); auto-suggests the next unused number; warns on duplicate
- **Copy to Clipboard** — all rows tab-separated
- **Export to CSV…** — full invoice log export
- Right-click any row for Copy Row / Copy Cell / Copy All

---

## Tab: Clients

| Column | Notes |
|--------|-------|
| Client Name | |
| Contact / Phone / Email | |
| Invoices | Count of invoices issued |
| Total Billed | Sum of all invoice totals |

Clients from `invoices.csv` not in `clients.csv` appear automatically.

---

## Tab: Ledger

Record money in/out that isn't an invoice (grants, fees, wages, etc.).

### Entry form fields

| Field | Notes |
|-------|-------|
| Date | DD/MM/YYYY |
| Type | `in` or `out` |
| Category | Dropdown (changes by type) |
| Amount | Positive number |
| Description | Required |
| Reference | Optional — invoice ref, receipt number, etc. |
| Notes | Free text |

**Summary bar** — running totals for In, Out, and Net.

### Buttons
- **Add Entry / Update Entry** — double-click a row to edit
- **Delete Selected**
- **Paste from Clipboard** — paste tab/CSV rows (date, type, category, description, amount, reference, notes)
- **Import from CSV…** — open a CSV file
- **Export to CSV…**

---

## Tab: Students

### Student Register sub-tab

| Column | Notes |
|--------|-------|
| ID | Auto-assigned |
| First / Last Name | Required for import |
| Email / Phone | |
| USI | Unique Student Identifier |
| Work Group | Department or team |
| Manager | Supervisor name |
| Emergency Contact / Phone | |
| Status | enrolled / completed / withdrawn / pending / rescheduled |

**Filter bar** — free-text search + status dropdown + **Show Deleted** toggle.

**Buttons**
- **Add Student / Edit Selected**
- **Delete Selected** — soft-delete (hidden, recoverable)
- **Restore Selected** — visible only when "Show Deleted" is on
- **Import XLSX…** — import from Excel tracker spreadsheet
- **Import CSV…** — import from CSV file
- **Paste Clipboard** — paste tab/CSV rows; name splitting handled automatically (see below)
- **Export CSV…**

#### Smart name splitting on paste

The paste parser handles these formats without any manual cleanup:

| Clipboard format | Result |
|-----------------|--------|
| `first_name, last_name, email` (3 cols) | Used directly |
| `name, email` — header `name` | Split on first space |
| `full_name, email` — header `full_name` | Split on first space |
| `John Smith\temail` — no header | First-column heuristic split |
| `Smith, John` — Last, First format | Inverted correctly |
| `Mary Jane Watson` | First = Mary, Last = Jane Watson |

#### Duplicate handling on import/paste

When a student with the same email or name already exists, the importer merges missing fields into the existing record rather than creating a duplicate.

### Certificate Budget sub-tab

Track a pool of funding for training certifications.

| Field | Notes |
|-------|-------|
| Pool name | Budget pool identifier |
| Date | Transaction date |
| Type | `topup` (adds funds) or `spend` (auto-posted on enrolment) |
| Amount | |
| Notes | Invoice reference, grant name, `enrolment_id=N` for auto-entries |

**Auto spend posting** — when a student is enrolled with a budget-drawing status, the cert cost is automatically posted as a `spend` entry against the course's pool. If the enrolment is deleted or the status changes to a zero-budget status, the spend entry is reversed.

**Soft delete** — budget entries can be soft-deleted and restored; cascade delete of a course soft-deletes all linked enrolment spend entries.

---

## Tab: Courses

### Course List sub-tab

Manage all training courses. Soft-deleted courses are hidden; use **Show Deleted** to view and restore them.

| Field | Notes |
|-------|-------|
| Course type | e.g. HLTAID011, HLTAID009 |
| Date | DD/MM/YYYY |
| Time | Optional start time |
| Location | |
| Trainer | |
| Max students | Capacity |
| **Cert cost ($)** | Per-student cost auto-deducted from the budget pool on enrolment |
| **Budget pool** | Which cert budget pool to draw from |
| Status | scheduled / confirmed / completed / cancelled |

**Cascade delete** — soft-deleting a course soft-deletes all its enrolments and their associated budget spend entries.

### Course Detail sub-tab

Opened by double-clicking a course in the list.

Shows course header info and the full enrolment list for that course.

#### Enrolment columns

| Column | Notes |
|--------|-------|
| Name / Email / Phone | |
| USI / Work Group / Manager | Pre-filled from Student Register if student exists |
| **Enrolment Status** | See status table above — drives budget and cert sign-off |
| Attendance | attended / absent / not recorded |
| Cert issued / Cert date | |
| **Cancellation notes** | Required for billed/reallocated statuses |
| Notes | General notes |

**Enrolment status label** in the add/edit dialog shows the budget impact live as you select a status.

**Status count bar** — Total · Active (budget-drawing) · Completed · Attended.

**Buttons**
- **Add Student / Edit Selected**
- **Delete Selected** — soft-delete (spend entry reversed automatically)
- **Restore Selected** — restores enrolment; spend re-posted if status draws budget
- **Paste Clipboard** — paste enrolment rows into the current course
- **Import CSV…**
- **Export Enrolments CSV…**
- **Certificate (selected)…** — generate a single Word (.docx) completion certificate
- **Batch Certificates…** — generate one .docx with all students (prompts to include/exclude zero-budget statuses)

### Booking Report sub-tab

Produce a cross-course booking report for selected dates.

1. **Select courses** — Ctrl+click for multiple; leave blank to include all
2. **Status filter** — narrow to a single status or show all
3. **Include zero-budget statuses** — toggle to hide cancelled & reallocated etc.
4. **Run Report** — populates colour-coded results table
5. **Summary bar** — count per status + estimated budget draw ($)
6. **Export CSV…** — full detail export (name, email, course, date, status, budget impact, notes)
7. **Copy to Clipboard** — tab-separated for Excel

#### Booking report columns

name · email · phone · course type · course date · location · trainer · enrolment status · attendance · cert issued · cert date · budget impact · cancellation notes · notes

### Course Reports sub-tab

Text summary of all courses — enrolment counts, attendance, certs issued, trainer summary.

---

## Tab: Reports

All sub-tabs support **Export CSV…** and full clipboard copy.

| Sub-tab | Contents |
|---------|---------|
| Business Summary | Revenue, GST collected, unpaid balance, invoice counts |
| Invoice Report | All invoices in a filterable grid |
| Ledger Report | All ledger entries with running balance |
| Students Report | Student counts by status |
| Cert Budget | Budget pool summary — topups vs spend, balance per pool |
| Audit Log | Structured audit trail: timestamp · action · table · record ID · detail |
| App Log | Live application log viewer (see below) |

### App Log sub-tab

- Reads `invoicer.log` in real time
- **Level filter** — show All / DEBUG / INFO / WARNING / ERROR / CRITICAL
- **Keyword search** — instant filter across all visible lines
- **Refresh** — reloads the log file
- **Export…** — save the current filtered view to a text file
- Colour-coded by severity (red = error/critical, amber = warning, grey = debug)

---

## Tools Menu

| Item | Action |
|------|--------|
| Settings… | Opens the Settings dialog |
| Manage Clients… | Client management dialog |
| Manage Service Catalogue… | Service item editor |
| Open Invoices Folder | Opens the invoices/ PDF folder in Explorer |
| Open Data Folder | Opens the data folder in Explorer |
| Reload All from Disk (F5) | Re-reads all CSV files without restarting |
| **Backup Now** | Run an immediate silent backup; shows destination folder |
| Export All Data… | Zip all CSVs + PDFs + logs + `config.json` for manual backup |
| Import Data… | Restore from a backup zip (auto-migrates schema) |
| Migrate from V1.8 folder/zip… | Import from a V1.8 or earlier data folder or zip; reports all schema changes |
| Import Students from XLSX… | Import from Excel student tracker spreadsheet |
| Import Legacy Students CSV… | Import from a flat legacy students CSV |

**Help menu**

| Item | Action |
|------|--------|
| About Invoice Generator… | Shows version number, data format, PDF engine, Python version |

---

## Settings Dialog

### Business tab
Business name, ABN, address, phone, email — all appear in the PDF header.

### Payment tab
Bank name, BSB, account number, account name — printed in the PDF payment section.

### Invoice tab
| Field | Effect |
|-------|--------|
| GST rate (%) | Applied to all taxable line items |
| Payment terms (days) | Default due date offset |
| Currency symbol | Prefix on all monetary values |
| Next invoice number | Starting number for new invoices |

### PDF tab
| Setting | Effect |
|---------|--------|
| Training Manager name | Appears on course completion certificates |
| Thank-you note | Printed at the bottom of every PDF |
| Not registered for GST | Prints italic disclaimer on PDF |
| PDF save location | Auto (silent) or Prompt (Save-As dialog) |
| Default folder | Where PDFs are saved; blank = `invoices/` subfolder |

### Reports tab
Colour scheme for generated PDF reports — header colour, accent colour, row stripe colour (all hex).  
Wording overrides — "Prepared by", footer note, organisation name override.

### Backup tab
| Setting | Default | Effect |
|---------|---------|--------|
| Enable automatic backups | Off | Master on/off switch |
| Frequency | daily | hourly / every 2h / every 4h / every 6h / every 12h / daily |
| Backup folder | `data_dir/backups/` | Any local or network path |
| Keep last N copies | 10 | Older zips pruned automatically |
| Backup on exit | On | Writes a final backup on every close |

Buttons: **Backup Now**, **Refresh list** (shows last 8 with size/timestamp), **Open folder**.

### Config tab
| Setting | Effect |
|---------|--------|
| Data directory | Where all CSV files are stored; blank = same folder as EXE |
| **OneDrive section** | Auto-detects OneDrive path; "Use OneDrive folder" sets data dir to `<OneDrive>\InvoicerData`; "Move existing data there…" copies files before switching |
| Invoice PDF save folder | Override where generated PDFs land |

---

## Course Completion Certificates

Generated as Word (.docx) files via **python-docx**.

Each certificate contains:
- Business name and logo area
- Student full name (large, prominent)
- Course type and date
- Location and trainer
- Training Manager signature block (name from Settings → Training Manager)

**Single certificate** — select a student row → Certificate (selected)…  
**Batch certificates** — one page per student in a single .docx → Batch Certificates…  
When running batch, if any students have zero-budget statuses (cancelled & reallocated etc.) the app asks whether to include or exclude them from the sign-off sheet.

---

## File Reference

### `settings.json`

```json
{
    "next_invoice_number": 1,
    "business_name": "Your Business Name",
    "business_abn": "",
    "business_address": "",
    "business_phone": "",
    "business_email": "",
    "bank_name": "",
    "bank_bsb": "",
    "bank_account": "",
    "bank_account_name": "",
    "gst_rate": 0.10,
    "payment_terms_days": 30,
    "currency_symbol": "$",
    "training_manager": "",
    "thank_you_note": "Thank you for your business!",
    "show_gst_not_registered": false,
    "pdf_save_mode": "auto",
    "pdf_save_dir": ""
}
```

### `config.json`

```json
{
    "data_dir": "C:\\Users\\you\\OneDrive\\InvoicerData"
}
```

Written beside the EXE. Leave `data_dir` blank (or omit) to store data in the same folder as the EXE.

### CSV schemas (current)

| File | Fields |
|------|--------|
| `invoices.csv` | invoice_number, invoice_date, due_date, client_name, client_address, notes, subtotal, gst, total, paid, paid_date, payment_note |
| `ledger.csv` | id, date, type, category, description, amount, reference, notes, deleted |
| `students.csv` | id, first_name, last_name, email, phone, usi, work_group, manager, emergency_contact, emergency_phone, course, enrolment_date, cert_cost, cert_issued_date, group_tag, status, notes, deleted |
| `cert_budgets.csv` | id, pool_name, date, type, amount, notes, deleted |
| `courses.csv` | id, course_type, course_date, course_time, location, trainer, max_students, cert_cost, pool_name, status, notes, deleted |
| `enrolments.csv` | id, course_id, student_id, first_name, last_name, email, phone, usi, work_group, manager, enrolment_status, attendance, cert_issued, cert_date, cancellation_notes, notes, deleted |
| `course_logs.csv` | id, course_id, timestamp, author, log_type, student_id, first_name, last_name, entry |
| `course_types.csv` | id, name, default_cert_cost, default_pool_name, notes |
| `audit.csv` | timestamp, user, action, table, record_id, detail |
| `clients.csv` | name, contact_name, phone, email, address |
| `service_items.csv` | name, description, unit_price, taxable |
| `custom_reports.json` | Saved custom report definitions (array) |

All CSV files are automatically migrated on startup — new columns are added with blank defaults and no existing data is lost.

---

## Version History

### v1.31 (current)

| Area | Change |
|------|--------|
| Logging | Expanded logging across all modules — `app_log.py` now writes startup banner (Python/OS/PID), dev console handler, `log_event()` and `log_summary()` helpers |
| Log files | Increased to 5 MB × 10 rotated files (was 2 MB × 5) |
| All tabs | Every tab now has a named logger; all `except` blocks log with `exc_info=True`; data mutations log via `log_event()` |
| Data store | `export_all` / `import_all` emit structured summaries; CSV read/write failures no longer silently swallowed |

### v1.30

| Area | Change |
|------|--------|
| Auto-backup | `AutoBackupManager` — silent scheduled backups via daemon thread; configurable frequency, folder, retention |
| Backup on exit | Optional final backup every time the app closes |
| Backup Now | Tools menu entry + Settings → Backup tab button |
| Backup tab | New Settings tab with full controls and backup list |

### v1.29

| Area | Change |
|------|--------|
| ATO Tax Report | Income/expense summary by financial year and quarter with GST 1/11 rule |
| Custom Report builder | Build, save, and export ad-hoc reports from any combination of data fields |
| Export coverage | `course_types.csv` and `custom_reports.json` added to `export_all` and `import_from_folder` |
| Reports tab | ATO Tax Report and Custom Report sub-tabs added |

### v1.28

| Area | Change |
|------|--------|
| Courses CSV import | Import courses + enrolments from a flat CSV |
| Batch certificates | Generate one .docx with all enrolled students (one page each) |
| Delivery record | Generate a Course Delivery Record PDF for proof-of-delivery |
| Course type catalogue | Manage reusable course types with default cert cost and pool |
| Create Course wizard | 3-step wizard: type → details → students |

### v1.9

| Area | Change |
|------|--------|
| Date pickers | All date fields use `DateEntry` with calendar popup + smart parser; displayed as dd/mm/yyyy |
| Student View | Read-only profile screen with Upcoming / Past enrolments split |
| Merge robustness | Merges re-point soft-deleted enrolments and blank-student_id rows — no class history lost |
| Budget deduction fix | `completed` status now correctly deducts cert cost |
| Ledger mirror | Budget deductions post matching `out` ledger entries; reversals remove them |
| About dialog | Help → About; version read from `VERSION` file |

### Migration (any version → v1.31)

`DataStore.migrate_all()` runs at every startup and after every import — adds missing columns, never removes data.

**Tools → Migrate from V1.8 folder/zip…** — choose a data folder or `.zip`; the app copies files and reports every schema change applied.

---

## Running the Tests

```powershell
python test_invoice.py
```

Runs **498 headless tests** — no GUI window required.

Coverage includes:

- Settings defaults and round-trip
- Invoice CRUD — save, PDF, counter, payment recording, Record Missing Invoice
- Client management — add/edit/delete, auto-fill, stats
- DataStore — all CSV schemas, migration (migrate_all idempotent), audit logging (table + record_id)
- Soft delete + restore — students, ledger, cert budgets, courses (cascade), enrolments
- Budget integrity — auto spend on enrol; reversal on delete/cancel; cascade course delete
- Ledger — CRUD, categories, running totals, soft delete/restore
- Students — USI, work group, manager, emergency contact; dedup merge
- Courses — CRUD, get, update, soft-delete cascade; course type catalogue
- Enrolments — CRUD, per-course filter, export CSV, status-driven spend
- Enrolment statuses — budget impact constants, zero-budget set, cert-sign set, pending
- Booking report — multi-course filter, budget values, cancellation notes, sorting
- Certificate generation — content check, batch, delivery record, filename suggestion
- Smart clipboard — tab/CSV parse, header detection, positional fallback
- Name splitting — First Last, Last First, multi-word, no-header heuristic
- Data import/export — zip backup (full coverage), XLSX student import, CSV round-trip
- `app_log` — setup_logging, get_logger, startup banner, file creation, re-pointing, write verification
- `_detect_onedrive` — returns non-empty path to real directory
- V1.5 migration — import_from_folder, all per-file schema upgrades, data integrity, idempotency
- Budget deduction — completed/enrolled/no-show all deduct; ledger mirror posted and reversed in sync
- Merge robustness — re-points soft-deleted + blank-student_id enrolments by name (no class history lost)
- Auto-backup — AutoBackupManager scheduling, pruning, run_now, apply_new_settings
- Settings dialog — SettingsDialog construction and all tab defaults

```
ALL 498 TESTS PASSED
```

---

## Customisation reference

| What to change | Where |
|----------------|-------|
| PDF colours / fonts / layout | `InvoiceApp._create_pdf()` |
| Default sample services | `InvoiceApp._ensure_environment()` |
| Default settings | `_DEFAULT_SETTINGS` in `invoice_gui.py` |
| Enrolment status list | `ENROLMENT_STATUSES` in `data_store.py` |
| Budget impact rules | `ENROLMENT_BUDGET_IMPACT` in `data_store.py` |
| Certificate layout | `cert_doc.py` |
| Recognised "full name" column headers | `_FULL_NAME_COLS` in `smart_clipboard.py` |
| Log rotation size / backup count | `setup_logging()` in `app_log.py` |
| Report PDF colour scheme | Settings → Reports tab |

---

## Module overview

| File | Role |
|------|------|
| `invoice_gui.py` | Main window, settings dialog, all menus, `InvoiceApp` lifecycle |
| `data_store.py` | All CSV schemas, paths, migration, CRUD, audit, import/export |
| `app_log.py` | Rotating file logger, startup banner, `log_event()`, `log_summary()`, global exception hook |
| `auto_backup.py` | `AutoBackupManager` — silent scheduled backup daemon |
| `date_utils.py` | `DateEntry` calendar widget + date parse/format helpers |
| `ledger_tab.py` | Ledger tab UI and logic |
| `students_tab.py` | Students tab (register, Student View, merge dialogs) + cert budget tab |
| `courses_tab.py` | Courses tab — list, detail, booking report, course reports, course type manager |
| `reports_tab.py` | Reports tab — business summary, ATO tax report, custom report builder, audit log, app log viewer |
| `cert_doc.py` | Word certificate generation (single, batch, delivery record) |
| `report_pdf.py` | PDF report generation (ReportLab) |
| `report_preview.py` | On-screen report preview before PDF/CSV export |
| `smart_clipboard.py` | Reusable clipboard / copy / paste / bulk-edit utilities for all treeviews |
| `inline_editor.py` | In-place cell editing for treeview tables |
| `app_theme.py` | Tkinter theme, colour constants, tag configuration |
| `test_invoice.py` | 498-test headless test suite |
| `VERSION` | Plain-text version string (shown in title/About) |
| `UPDATE_PLAN.md` | Feature roadmap and priority cleanup queue |
| `InvoiceGenerator.spec` | PyInstaller build spec |
| `installer/InvoiceGenerator.iss` | Inno Setup installer script |

---

## Distribution (EXE)

See [`DISTRIBUTION.md`](DISTRIBUTION.md) for full build, packaging, and upgrade instructions.

---

## Troubleshooting

### The EXE won’t start (nothing happens, or OneDrive errors)

The built EXE is often stored in a OneDrive folder. OneDrive can keep the file as an online-only placeholder, which prevents Windows from launching it reliably.

**Fix:** run the local launcher:

```bat
run_local.bat
```

This copies `dist\Invoice Generator v1.49.exe` to `C:\InvoicerData\InvoiceGenerator.exe` and launches it from there, using `C:\InvoicerData` as the data directory. This avoids OneDrive sync issues.

If it still won’t start, run the diagnostic script and share the log:

```bat
python diagnose_launch.py
```

The log is saved to `C:\InvoicerData\launch_diagnose.log`.
