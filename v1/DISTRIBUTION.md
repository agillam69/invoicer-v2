# EXE Distribution — Invoice Generator v1.33

## Overview

The goal is a single `InvoiceGenerator.exe` that any Windows user can run with no Python or library installation.  
**PyInstaller** bundles the interpreter, all packages, and the script into one file (~27 MB).  
An optional **Inno Setup** script (`installer/InvoiceGenerator.iss`) wraps it in a standard Windows installer.

---

## Prerequisites (build machine only)

```powershell
pip install pyinstaller reportlab python-docx openpyxl
```

Confirm:
```powershell
python --version          # 3.8–3.12 recommended
pyinstaller --version     # 6.x
python -c "import reportlab; print(reportlab.Version)"
python -c "import docx; print('docx ok')"
python -c "import openpyxl; print('openpyxl ok')"
```

---

## Build

The spec file `InvoiceGenerator.spec` is already committed. Just run:

```powershell
pyinstaller InvoiceGenerator.spec
```

Output: `dist\InvoiceGenerator.exe`

Build artefacts (`build\`, `__pycache__`) can be deleted after a successful build.

### What the spec bundles

All application modules are listed as `hiddenimports` so PyInstaller includes them even though they are imported dynamically:

```
data_store, app_log, auto_backup, date_utils,
ledger_tab, students_tab, reports_tab, courses_tab,
cert_doc, smart_clipboard, report_pdf, report_preview, inline_editor, app_theme,
startup_manager,
docx, docx.shared, docx.enum.text, docx.enum.table,
docx.oxml, docx.oxml.ns,
openpyxl, openpyxl.styles, openpyxl.utils, openpyxl.workbook,
reportlab.graphics, reportlab.graphics.barcode,
reportlab.graphics.charts, reportlab.lib.pagesizes,
reportlab.lib.styles, reportlab.lib.units,
reportlab.platypus, reportlab.pdfgen
```

Heavy unused packages (matplotlib, numpy, PyQt5/6, IPython, etc.) are in `excludes` to keep the EXE small.

---

## Test before building

Run the full test suite — **all 498 tests must pass** before producing a distribution build:

```powershell
python test_invoice.py
```

Expected output: `ALL 498 TESTS PASSED`

Then do a smoke test of the EXE:

1. Copy `dist\InvoiceGenerator.exe` to a **clean folder** (ideally a machine without Python).
2. Launch it — on first run the app creates all data files beside the EXE.
3. Verify:
   - PDF invoice generation
   - Word certificate generation (Courses → Course Detail → Certificate)
   - Settings save/load
   - All tabs open without errors
   - Paste-from-clipboard works in Students and Enrolments
   - App Log tab in Reports shows log entries

> **Data location:** all files are created in the **folder the EXE lives in** by default, not inside the EXE. The data folder can be changed in Settings → Config (e.g. pointed at OneDrive). Files are plain CSV/JSON — editable in any spreadsheet or text editor.

---

## Data files created on first run

| File | Contents |
|------|---------|
| `config.json` | Data folder path (beside EXE; blank = same folder) |
| `settings.json` | Business info, GST, PDF and training manager settings |
| `clients.csv` | Client records |
| `service_items.csv` | Service catalogue |
| `invoices.csv` | Invoice log (inc. payment status) |
| `invoices/` | Generated PDF invoices |
| `ledger.csv` | Non-invoice financial transactions |
| `students.csv` | Student register |
| `cert_budgets.csv` | Certificate budget pool entries |
| `courses.csv` | Course schedule (inc. cert_cost, pool_name per course) |
| `enrolments.csv` | Course enrolments with status and cancellation notes |
| `course_logs.csv` | Per-course log entries |
| `audit.csv` | Structured audit trail (action, table, record_id) |
| `invoicer.log` | Rotating application log (5 MB × 10 files) |
| `course_types.csv` | Course type catalogue |
| `custom_reports.json` | Saved custom report definitions |
| `backups/` | Auto-backup zip files (default location) |

---

## Package for distribution

### Option A — Folder drop (simplest)

```
InvoiceGenerator\
    InvoiceGenerator.exe
    README.md
```

Zip and share. Users unzip anywhere and run the `.exe`.

### Option B — Installer (recommended)

The script `installer\InvoiceGenerator.iss` produces a standard Windows installer via **Inno Setup** (free — [jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php)).

```powershell
# From the installer\ folder, or use the Inno Setup GUI:
iscc InvoiceGenerator.iss
```

Output: `installer\InvoiceGenerator_Setup_<version>.exe`

The installer:
- Creates a Start Menu shortcut (optional desktop shortcut)
- Bundles **only the EXE** — no data files (users start fresh or import a backup zip)
- Leaves user data intact on uninstall

#### Updating the version number in the installer

Edit the `#define AppVersion` line at the top of `installer\InvoiceGenerator.iss`:

```iss
#define AppVersion "1.32"
```

---

## Migrating data between versions

### From any earlier version → v1.32

Migration is fully automatic — new CSV columns are added on startup with blank defaults.

**Option A — Replace EXE in place (recommended)**

1. Copy `InvoiceGenerator.exe` into the same folder as the existing EXE and data files.
2. Run it. `migrate_all()` silently adds any missing columns.

**Option B — New folder, import data**

1. In the old app: **Tools → Export All Data…** → save zip.
2. Install v1.32 EXE in a new folder.
3. **Tools → Import Data…** → select the zip. Schema migration runs automatically.

**Option C — Migrate from folder via GUI**

1. In v1.32: **Tools → Migrate from V1.8 folder/zip…**
2. Point at the old data folder (or zip).
3. App copies files and shows a plain-English report of all schema upgrades applied.

### From any version → OneDrive

1. In the app: **Settings → Config → Use OneDrive folder** (auto-detected).
2. Click **Move existing data there…** — copies all files, switches the data path.
3. Save settings. From this point all CSV writes go to the OneDrive folder and sync automatically.

---

## Keeping it up to date

When code changes:

1. Run `python test_invoice.py` — confirm all **498 tests** pass.
2. Re-run `pyinstaller InvoiceGenerator.spec`.
3. Bump `AppVersion` in `installer\InvoiceGenerator.iss` if distributing an installer.
4. Re-run `iscc InvoiceGenerator.iss` to produce the new setup EXE.
5. Optionally re-zip: `Compress-Archive -Path dist\* -DestinationPath InvoiceGenerator.zip -Force`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` at runtime | Add the missing module to `hiddenimports` in `InvoiceGenerator.spec` and rebuild |
| App opens then closes instantly | Temporarily change `console=False` to `console=True` in the spec to see error output; or check `invoicer.log` |
| `docx` / certificate not working | Ensure `python-docx` is installed on the build machine; check `docx.*` entries in `hiddenimports` |
| Antivirus flags the EXE | Expected for unsigned PyInstaller builds; sign with a code-signing certificate for production use |
| EXE size unexpectedly large | Check `excludes` list in the spec; avoid importing unused heavy packages |
| Log file not created | Check write permissions on the data folder; see `app_log.setup_logging()` |
| OneDrive path not detected | Check `%OneDrive%` environment variable is set; or browse manually in Settings → Config |

---

## Quick-reference

```powershell
# Run tests
python test_invoice.py

# Build EXE (uses committed spec)
pyinstaller InvoiceGenerator.spec

# Zip for distribution
Compress-Archive -Path dist\* -DestinationPath InvoiceGenerator.zip -Force

# Build installer (requires Inno Setup)
iscc installer\InvoiceGenerator.iss

# Output locations
dist\InvoiceGenerator.exe
InvoiceGenerator.zip
installer\InvoiceGenerator_Setup_1.32.exe
```

