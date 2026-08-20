# Invoicer V2 — Build Plan

Derived from `Invoice_Receipt_Manager_AI_BUILD_SPEC.md`, cross-referenced against V1
(`agillam69/Invoice-Generator`, Python/Tkinter, v1.10).

## 1. Repository

- **New repo:** `agillam69/invoicer-v2` (suggested name; the Python package is `invoice_manager`).
- Clean history, no V1 code copied wholesale. V1 is referenced, not forked — its useful logic is
  ported deliberately, file by file, into the layered structure below.
- V1's `StudentTracker/` subtree (C# WPF) is out of scope entirely and is not carried over.

**Blocker:** I have no GitHub API token on this machine and `gh` is not installed, so I cannot
create the remote repo myself. Either you create an empty `invoicer-v2` repo (no README, no
.gitignore) and I push to it, or you give me a PAT with `repo` scope and I create it.

## 2. Stack (from spec Part C, all versions pinned in `pyproject.toml`)

| Area | Choice |
|---|---|
| Language | Python 3.12 |
| GUI | PySide6 |
| DB | SQLite (foreign keys ON per connection) |
| Data access | SQLAlchemy 2.x ORM + Alembic migrations |
| PDF | ReportLab |
| PDF verification | pypdf + pdfplumber, Poppler render-to-PNG for visual checks |
| CSV/Excel | stdlib `csv` + openpyxl |
| Passwords | argon2-cffi (Argon2id) |
| Money | integer cents, `Decimal` for all intermediate maths |
| Tests | pytest, pytest-qt, Hypothesis, pytest-cov |
| Lint/format/types | ruff (lint + format), mypy strict on `domain/` and `application/` |
| Packaging | PyInstaller (one-file, versioned exe name, embedded icon) |
| Installer | Inno Setup |
| CI | GitHub Actions on `windows-latest`: ruff, mypy, pytest with coverage gates |

Layout exactly as spec §7 (`domain/`, `application/`, `persistence/`, `documents/`, `ui/`,
`infrastructure/`, `tests/{unit,domain,integration,migration,pdf,gui,e2e,fixtures}`).
Hard rule enforced by review: no calculation, numbering, status or migration logic in UI handlers.

## 3. What we take from V1, and what we deliberately leave behind

**Port (logic worth keeping, rewritten into the new layers):**

- `date_utils.py` — the tolerant date parser (dd/mm/yyyy, d/m/yy, `25Jun2026`, ISO) and the
  calendar-entry widget behaviour. Becomes `domain/validation.py` + a PySide6 date field.
- `smart_clipboard.py` — right-click Copy Row/Cell/All, `Ctrl+C`/`Ctrl+A`, CSV/TSV paste
  detection. Becomes a reusable `ui/common/` table mixin, plus CSV formula-injection guarding.
- `report_pdf.py` / invoice PDF layout in `invoice_gui.py` — the visual layout (business header,
  payment block, thank-you note, GST-not-registered disclaimer) is the starting point for the new
  A4 ReportLab templates.
- `app_log.py` — rotating log + global exception hook → `infrastructure/logging_setup.py`.
- Settings surface (business / payment / invoice / PDF / config / reports tabs) → the eight
  Settings sections in the spec, now validated and with working Cancel.
- `InvoiceGenerator.spec` and `installer/InvoiceGenerator.iss` as the basis for the new
  PyInstaller/Inno configuration.
- OneDrive detection + "move data there" flow, now with the spec's warning + single-instance lock.

**Drop:**

- CSV-as-database (`data_store.py`, ~56 KB) — replaced by SQLite + Alembic.
- The 113 KB `invoice_gui.py` monolith — replaced by the layered UI.
- Everything student/course/certificate/budget: `students_tab.py`, `courses_tab.py`,
  `cert_doc.py`, `cert_budgets.csv`, `enrolments.csv`, the enrolment-status/budget-impact engine,
  booking reports, and the "certificate credit" model. Per spec §3 none of it is reimplemented.
- Manually-toggled `paid` flag and the `paid`/`paid_date`/`payment_note` columns — V2 derives
  status from payments and credits, and payments become first-class rows with receipts.

## 4. Migration data — needs your input

The spec (§36) expects a supplied `Invoice_Receipt_Manager_Import_Bundle` (manifest.json,
clients.csv, invoices.csv, invoice_items.csv, payments.csv, receipts.csv, documents.csv,
migration_issues.csv, source_documents/). **That bundle is not in the repo and was not attached.**

What the repo does contain is `old_data_import.zip`, and it does not match the spec baseline:

| | Spec Part H baseline | `old_data_import.zip` |
|---|---|---|
| Invoices | INV-0001 $600, 0002 $112.50, 0003 $120, 0004 $85 | one row: `0001`, 05/06/2026, $500 + $50 GST = $550 |
| GST | not registered (rate 0.0) | invoice carries $50 GST |
| Clients | incl. Chelsea Carr | Town and Country Medical, Specialist Event Medical only |
| PDFs | INV-0001..0004 + receipt 0004-R | `invoice_0001..0003.pdf` |
| Next number | ≥ 5 | 2 |

So this zip is an old snapshot, not the live V1 data. To build the importer against real data I
need **either** the import bundle described in the spec, **or** a zip of your current V1 data
folder (`invoices.csv`, `clients.csv`, `service_items.csv`, `ledger.csv`, `settings.json`, the
`invoices/` PDF folder) plus the NAB advice and receipt 0004-R evidence. Until then I build the
importer against the spec's contract with synthetic fixtures, and reconcile against your real data
as a separate step.

## 5. Phases

Each phase ends green: ruff + mypy clean, its own tests passing, nothing merged that leaves
partial financial state. Estimates are in my own working sessions, not calendar time.

| Phase | Content | Est. |
|---|---|---|
| 0 — Baseline | Repo, CI, decision log (spec Part L answers recorded), traceability matrix skeleton (every `FR-*` → test id), PDF mockups | 1 |
| 1 — Foundation | pyproject/lint/test harness, SQLite + Alembic initial schema (all entities from Part F, constraints + indexes), money/date/validation domain, Argon2id login + users, audit + app log, app shell with the 8-item nav rail | 1–2 |
| 2 — Migration & clients | Bundle importer (preflight → review queue → transactional commit → reconciliation report), legacy folder/ZIP scanner, non-destructive source hashing, idempotent re-import, clients incl. merge + duplicate detection, document store with sha256 | 1–2 |
| 3 — Invoices | Service catalogue, draft editor, transactional issue + number reservation, immutable issued snapshot, invoice PDF, invoice list + context actions (reissue/cancel/void/duplicate/relink/register-missing) | 2 |
| 4 — Payments, receipts, credits | Multiple/partial payments, overpayment warning, reversal with reason, receipt generated from saved payment (unique number, reissue keeps number), credit notes, derived status/balance | 1–2 |
| 5 — Ledger & reports | Categories, manual income/expense with attachments, dashboard cards, invoice/payment/receipt registers, ageing, client statement, P&L, GST by AU FY/quarter, double-count prevention, CSV/PDF export | 1–2 |
| 6 — Hardening & release | Backup/restore incl. clean-machine disaster-recovery test, OneDrive safeguards + instance lock, performance run at 10k invoices, security tests (ZIP-slip, path traversal, CSV injection, throttling), PyInstaller + Inno installer, user guide, release checklist | 1–2 |

Testing is written inside each phase, not bolted on: financial rules unit-tested below the GUI,
golden PDFs for the seven documents in spec §50, and the ten end-to-end scenarios in §56 as the
release gate.

## 6. Decisions I'm proceeding on (spec Part L, unless you say otherwise)

Permanent number at issue; receipt offered immediately after payment with reissue; local DB with
OneDrive backups; attachments copied into managed storage; NAB advice treated as INV-0001 payment
confirmation; INV-0002/0003 imported as flagged legacy payments; `0001-1`/`ERROR` kept only as a
migration issue; GST **not** registered (so documents print `INVOICE`, not `TAX INVOICE`);
GST-exclusive price entry.

## 7. What I need from you to start Phase 0

1. Repo creation: empty `invoicer-v2` from you, or a PAT.
2. Confirm the repo name and that V1 = the Python app at the root of `Invoice-Generator`.
3. The import bundle or a zip of your live V1 data folder (§4).
