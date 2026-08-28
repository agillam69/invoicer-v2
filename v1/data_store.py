"""
data_store.py
=============
Central data layer for Invoice Generator.

Provides schemas and CSV storage for invoices, ledger entries, clients, users, audit records, service items, and application settings.
"""

import csv
import json
import logging
import os
import zipfile
import shutil
from datetime import datetime
from pathlib import Path

from app_log import get_logger as _get_logger, log_event as _log_event, log_summary as _log_summary
_log = _get_logger('data_store')

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------
INVOICE_FIELDS = [
    'invoice_number', 'invoice_date', 'due_date', 'client_name',
    'client_address', 'notes', 'subtotal', 'gst', 'total',
    'paid', 'paid_date', 'payment_note', 'invoice_status', 'pdf_path',
]

INVOICE_STATUSES = ['unpaid', 'paid', 'cancelled', 'void']

LEDGER_FIELDS = [
    'id', 'date', 'type', 'category', 'description',
    'amount', 'reference', 'notes', 'deleted',
]


AUDIT_FIELDS = [
    'timestamp', 'user', 'action', 'table', 'record_id', 'detail',
]

CLIENT_FIELDS = ['name', 'contact_name', 'phone', 'email', 'address']


USER_FIELDS = [
    'id', 'username', 'password', 'role', 'created_at',
]


# ---------------------------------------------------------------------------
# Config defaults (config.json — separate from settings.json)
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG = {
    'data_dir': '',        # blank = same folder as exe/script
    'pdf_save_mode': 'auto',
    'pdf_save_dir': '',
}


class DataStore:
    """Manages all file paths and provides CSV read/write helpers."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.config_path = base_path / 'config.json'
        self.config = self._load_config()

        # Resolve data directory
        data_dir_str = self.config.get('data_dir', '').strip()
        self.data_dir = Path(data_dir_str) if data_dir_str else base_path
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.settings_path       = self.data_dir / 'settings.json'
        self.service_items_path  = self.data_dir / 'service_items.csv'
        self.clients_path        = self.data_dir / 'clients.csv'
        self.invoices_csv_path   = self.data_dir / 'invoices.csv'
        self.ledger_path         = self.data_dir / 'ledger.csv'
        self.audit_path          = self.data_dir / 'audit.csv'
        self.invoices_dir        = self.data_dir / 'invoices'
        self.users_path          = self.data_dir / 'users.csv'

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except FileNotFoundError:
            loaded = {}
        except Exception as e:
            _log.warning('Could not read config.json: %s', e)
            loaded = {}
        cfg = dict(_DEFAULT_CONFIG)
        cfg.update(loaded)
        return cfg

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def update_data_dir(self, new_dir: str):
        """Change data directory and save config. Does NOT move existing files."""
        self.config['data_dir'] = new_dir.strip()
        self.save_config()
        # Re-resolve all paths
        data_dir_str = self.config['data_dir']
        self.data_dir = Path(data_dir_str) if data_dir_str else self.base_path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path      = self.data_dir / 'settings.json'
        self.service_items_path = self.data_dir / 'service_items.csv'
        self.clients_path       = self.data_dir / 'clients.csv'
        self.invoices_csv_path  = self.data_dir / 'invoices.csv'
        self.ledger_path        = self.data_dir / 'ledger.csv'
        self.audit_path         = self.data_dir / 'audit.csv'
        self.invoices_dir       = self.data_dir / 'invoices'
        self.users_path          = self.data_dir / 'users.csv'

    # ------------------------------------------------------------------
    # Generic CSV helpers
    # ------------------------------------------------------------------
    def _read_csv(self, path: Path, fields: list) -> list:
        if not path.exists():
            return []
        try:
            with open(path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    record = {k: '' for k in fields}
                    record.update({k: v for k, v in row.items() if k in fields})
                    rows.append(record)
            return rows
        except Exception as e:
            _log.error('Failed to read CSV %s: %s', path, e, exc_info=True)
            return []

    def _write_csv(self, path: Path, fields: list, rows: list):
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            _log.error('Failed to write CSV %s: %s', path, e, exc_info=True)

    def _append_csv(self, path: Path, fields: list, row: dict):
        file_exists = path.exists()
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    # ------------------------------------------------------------------
    # Schema migration
    # ------------------------------------------------------------------
    def migrate_all(self) -> dict:
        """
        Run all schema migration checks.
        Returns a report dict: {filename: [added_columns]} for any file
        that needed upgrading. Empty list means file was already current.
        """
        pairs = [
            (self.invoices_csv_path,  INVOICE_FIELDS),
            (self.ledger_path,        LEDGER_FIELDS),
            (self.audit_path,         AUDIT_FIELDS),
            (self.clients_path,       CLIENT_FIELDS),
            (self.users_path,         USER_FIELDS),
        ]
        report = {}
        for path, fields in pairs:
            added = self._migrate_csv(path, fields)
            if added:
                report[path.name] = added
                _log.info('Migrated %s: added columns %s', path.name, added)
        return report

    def _migrate_csv(self, path: Path, fields: list) -> list:
        """Add missing columns to an existing CSV without losing data.
        Returns list of column names that were added (empty if none)."""
        if not path.exists():
            return []
        try:
            with open(path, 'r', newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
            if not rows:
                return []
            existing_fields = list(rows[0].keys())
            missing = [f for f in fields if f not in existing_fields]
            if not missing:
                return []
            for row in rows:
                for col in missing:
                    row[col] = ''
            self._write_csv(path, existing_fields + missing, rows)
            return missing
        except Exception as e:
            _log.error('Migration failed for %s: %s', path, e, exc_info=True)
            return []

    def import_from_folder(self, src_dir: Path, overwrite: bool = True) -> dict:
        """
        Import data from a plain folder (e.g. a V1.5 data directory).
        Copies recognised CSV/JSON files then runs migrate_all().
        Returns {'copied': [...], 'skipped': [...], 'migrated': {file: [cols]}}
        """
        src_dir = Path(src_dir)
        # Canonical filenames we know about
        known_files = [
            'settings.json', 'service_items.csv', 'clients.csv',
            'invoices.csv', 'ledger.csv', 'audit.csv', 'users.csv',
        ]
        copied, skipped = [], []
        for name in known_files:
            src = src_dir / name
            if not src.exists():
                continue
            dest = self.data_dir / name
            if dest.exists() and not overwrite:
                skipped.append(name)
                continue
            shutil.copy2(src, dest)
            copied.append(name)
        # Also copy invoices/ PDF subfolder if present
        src_inv = src_dir / 'invoices'
        if src_inv.is_dir():
            dest_inv = self.invoices_dir
            dest_inv.mkdir(parents=True, exist_ok=True)
            for pdf in src_inv.glob('*.pdf'):
                dest_pdf = dest_inv / pdf.name
                if not dest_pdf.exists() or overwrite:
                    shutil.copy2(pdf, dest_pdf)
                    copied.append(f'invoices/{pdf.name}')
        migration_report = self.migrate_all()
        self.audit('import_from_folder', str(src_dir))
        return {'copied': copied, 'skipped': skipped, 'migrated': migration_report}

    # ------------------------------------------------------------------
    # Initialise missing files
    # ------------------------------------------------------------------
    def ensure_files(self):
        """Create all required CSV/dir stubs if they don't exist."""
        self.invoices_dir.mkdir(exist_ok=True)

        stubs = [
            (self.invoices_csv_path,  INVOICE_FIELDS),
            (self.ledger_path,        LEDGER_FIELDS),
            (self.audit_path,         AUDIT_FIELDS),
            (self.clients_path,       CLIENT_FIELDS),
            (self.users_path,         USER_FIELDS),
        ]
        for path, fields in stubs:
            if not path.exists():
                self._write_csv(path, fields, [])
        self.ensure_default_user()

        if not self.service_items_path.exists():
            self._write_csv(self.service_items_path,
                            ['description', 'unit_price', 'taxable'],
                            [{'description': 'First Aid Training',          'unit_price': '300.00', 'taxable': 'yes'},
                             {'description': 'Clinical Cover (per hour)',   'unit_price': '100.00', 'taxable': 'yes'},
                             {'description': 'Course Completion Certificate','unit_price': '25.00',  'taxable': 'no'}])

        if not self.settings_path.exists():
            with open(self.settings_path, 'w', encoding='utf-8') as _f:
                json.dump({}, _f)

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------
    def audit(self, action: str, detail: str = '', user: str = 'app',
               table: str = '', record_id: str = ''):
        row = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user':      user,
            'action':    action,
            'table':     table,
            'record_id': record_id,
            'detail':    detail,
        }
        self._append_csv(self.audit_path, AUDIT_FIELDS, row)
        _log.info('[audit] %s  table=%s  id=%s  %s', action, table or '-',
                  record_id or '-', detail)

    def read_audit(self) -> list:
        return self._read_csv(self.audit_path, AUDIT_FIELDS)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------
    def read_invoices(self) -> list:
        return self._read_csv(self.invoices_csv_path, INVOICE_FIELDS)

    def append_invoice(self, row: dict):
        row.setdefault('invoice_status', 'unpaid')
        row.setdefault('pdf_path', '')
        self._append_csv(self.invoices_csv_path, INVOICE_FIELDS, row)
        self.audit('invoice_saved', f"#{row.get('invoice_number')} {row.get('client_name')}")
        _log_event('invoice', 'created', f"#{row.get('invoice_number')} {row.get('client_name')} total={row.get('total')}")

    def update_invoice(self, invoice_number: str, updates: dict):
        rows = self.read_invoices()
        for row in rows:
            if row['invoice_number'] == invoice_number:
                row.update(updates)
        self._write_csv(self.invoices_csv_path, INVOICE_FIELDS, rows)
        self.audit('invoice_updated', f"#{invoice_number} {list(updates.keys())}")

    def invoice_pdf_path(self, invoice_number: str, default_dir: Path = None) -> Path:
        """Return the PDF path for an invoice, honouring a custom pdf_path override."""
        row = next((r for r in self.read_invoices()
                    if r.get('invoice_number') == invoice_number), None)
        if row and row.get('pdf_path'):
            p = Path(row['pdf_path'])
            if p.exists():
                return p
        base = default_dir or self.invoices_dir
        return base / f'invoice_{invoice_number}.pdf'

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------
    def read_clients(self) -> list:
        return self._read_csv(self.clients_path, CLIENT_FIELDS)

    def write_clients(self, clients: list):
        self._write_csv(self.clients_path, CLIENT_FIELDS, clients)
        self.audit('clients_saved', f"{len(clients)} records")

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def read_users(self) -> list:
        return self._read_csv(self.users_path, USER_FIELDS)

    def write_users(self, users: list):
        self._write_csv(self.users_path, USER_FIELDS, users)

    def ensure_default_user(self):
        """Create a default admin user if no users exist."""
        users = self.read_users()
        if users:
            return
        self._write_csv(self.users_path, USER_FIELDS, [{
            'id': '1', 'username': 'admin', 'password': 'Admin',
            'role': 'admin', 'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }])

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """Return the user record if credentials match, else None."""
        for u in self.read_users():
            if u.get('username', '').strip() == username.strip() and \
               u.get('password', '').strip() == password.strip():
                return u
        return None

    def append_user(self, row: dict) -> str:
        all_rows = self.read_users()
        if not row.get('id'):
            row['id'] = str(len(all_rows) + 1)
        row.setdefault('role', 'user')
        row.setdefault('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self._append_csv(self.users_path, USER_FIELDS, row)
        self.audit('user_added', row.get('username', ''), table='users', record_id=row['id'])
        return row['id']

    def update_user(self, user_id: str, updates: dict):
        rows = self.read_users()
        for row in rows:
            if row['id'] == user_id:
                row.update(updates)
        self._write_csv(self.users_path, USER_FIELDS, rows)
        self.audit('user_updated', str(list(updates.keys())), table='users', record_id=user_id)

    def delete_user(self, user_id: str):
        """Permanently delete a user row."""
        rows = self.read_users()
        kept = [r for r in rows if r['id'] != user_id]
        self._write_csv(self.users_path, USER_FIELDS, kept)
        self.audit('user_deleted', '', table='users', record_id=user_id)

    # ------------------------------------------------------------------
    # Ledger
    # ------------------------------------------------------------------
    def read_ledger(self, include_deleted: bool = False) -> list:
        rows = self._read_csv(self.ledger_path, LEDGER_FIELDS)
        if not include_deleted:
            rows = [r for r in rows if r.get('deleted', '') != '1']
        return rows

    def append_ledger(self, row: dict) -> str:
        all_rows = self._read_csv(self.ledger_path, LEDGER_FIELDS)
        if not row.get('id'):
            row['id'] = str(len(all_rows) + 1)
        _log.debug('append_ledger: id=%s type=%s amount=%s', row['id'], row.get('type'), row.get('amount'))
        row.setdefault('deleted', '')
        self._append_csv(self.ledger_path, LEDGER_FIELDS, row)
        self.audit('ledger_added',
                   f"{row.get('type')} {row.get('amount')} \u2013 {row.get('description')}",
                   table='ledger', record_id=row['id'])
        return row['id']

    def update_ledger(self, entry_id: str, updates: dict):
        rows = self._read_csv(self.ledger_path, LEDGER_FIELDS)
        for row in rows:
            if row['id'] == entry_id:
                row.update(updates)
        self._write_csv(self.ledger_path, LEDGER_FIELDS, rows)
        self.audit('ledger_updated', str(list(updates.keys())),
                   table='ledger', record_id=entry_id)

    def delete_ledger(self, entry_id: str):
        """Soft-delete."""
        rows = self._read_csv(self.ledger_path, LEDGER_FIELDS)
        for r in rows:
            if r['id'] == entry_id:
                r['deleted'] = '1'
        self._write_csv(self.ledger_path, LEDGER_FIELDS, rows)
        self.audit('ledger_deleted', '', table='ledger', record_id=entry_id)

    def restore_ledger(self, entry_id: str):
        rows = self._read_csv(self.ledger_path, LEDGER_FIELDS)
        for r in rows:
            if r['id'] == entry_id:
                r['deleted'] = ''
        self._write_csv(self.ledger_path, LEDGER_FIELDS, rows)
        self.audit('ledger_restored', '', table='ledger', record_id=entry_id)

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def export_all(self, zip_path: Path):
        """
        Bundle ALL data, settings, config, invoice PDFs and log files into a
        structured zip for backup / transfer.

        Zip layout
        ----------
        manifest.json          — export metadata
        data/                  — all CSV data files
        data/settings.json     — application settings
        data/config.json       — data-directory config
        invoices/              — generated invoice PDFs
        logs/                  — rotating app log files (invoicer.log*)
        """
        _log.info('export_all started: %s', zip_path)
        self.ensure_files()

        # ── Data files ──────────────────────────────────────────────────
        data_files = [
            self.settings_path,
            self.invoices_csv_path,
            self.ledger_path,
            self.audit_path,
            self.service_items_path,
            self.clients_path,
            self.users_path,
        ]

        manifest = {
            'export_version': '2',
            'exported_at':    datetime.now().isoformat(timespec='seconds'),
            'app_version':    (self.base_path / 'VERSION').read_text(encoding='utf-8').strip()
                              if (self.base_path / 'VERSION').exists() else '',
            'data_dir':       str(self.data_dir),
            'files':          [],
        }

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:

            # CSV / JSON data
            for p in data_files:
                if p.exists():
                    arc = f'data/{p.name}'
                    zf.write(p, arc)
                    manifest['files'].append(arc)

            # config.json (may live at base_path, one level up from data_dir)
            if self.config_path.exists():
                zf.write(self.config_path, 'data/config.json')
                manifest['files'].append('data/config.json')

            # Invoice PDFs
            if self.invoices_dir.exists():
                for pdf in sorted(self.invoices_dir.glob('*.pdf')):
                    arc = f'invoices/{pdf.name}'
                    zf.write(pdf, arc)
                    manifest['files'].append(arc)

            # App log files  (invoicer.log, invoicer.log.1 … invoicer.log.5)
            log_base = self.data_dir / 'invoicer.log'
            log_candidates = [log_base] + [
                self.data_dir / f'invoicer.log.{i}' for i in range(1, 6)
            ]
            for lp in log_candidates:
                if lp.exists():
                    arc = f'logs/{lp.name}'
                    zf.write(lp, arc)
                    manifest['files'].append(arc)

            # Write manifest last
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))

        n_data = len([f for f in manifest['files'] if f.startswith('data/')])
        n_pdf  = len([f for f in manifest['files'] if f.startswith('invoices/')])
        n_log  = len([f for f in manifest['files'] if f.startswith('logs/')])
        _log_summary('export_all', {'data': n_data, 'pdfs': n_pdf, 'logs': n_log, 'total': len(manifest['files'])})
        self.audit('export', str(zip_path))

    def import_all(self, zip_path: Path, overwrite: bool = False):
        """
        Extract a backup zip into the data directory.
        Supports both the new structured layout (v2, with manifest.json) and
        legacy flat zips (v1).
        If overwrite=False, only imports files that don't already exist.
        Returns list of (filename, action) tuples.
        """
        results = []

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = set(zf.namelist())

            # Detect layout version
            is_v2 = 'manifest.json' in names

            for arc_name in sorted(names):
                if arc_name == 'manifest.json':
                    continue  # metadata only

                # Resolve destination path based on zip layout
                if is_v2:
                    if arc_name.startswith('data/'):
                        fname = arc_name[len('data/'):]
                        if fname == 'config.json':
                            dest = self.config_path
                        else:
                            dest = self.data_dir / fname
                    elif arc_name.startswith('invoices/'):
                        dest = self.invoices_dir / Path(arc_name).name
                    elif arc_name.startswith('logs/'):
                        dest = self.data_dir / Path(arc_name).name
                    else:
                        dest = self.data_dir / arc_name
                else:
                    # Legacy flat layout
                    if arc_name.startswith('invoices/'):
                        dest = self.invoices_dir / Path(arc_name).name
                    else:
                        dest = self.data_dir / arc_name

                dest.parent.mkdir(parents=True, exist_ok=True)

                if dest.exists() and not overwrite:
                    results.append((arc_name, 'skipped'))
                    continue

                with zf.open(arc_name) as src, open(dest, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                results.append((arc_name, 'imported'))
                _log.debug('import_all: imported %s', arc_name)

        self.migrate_all()
        n_imported = sum(1 for _, a in results if a == 'imported')
        n_skipped  = sum(1 for _, a in results if a == 'skipped')
        _log_summary('import_all', {'imported': n_imported, 'skipped': n_skipped, 'zip': zip_path.name})
        self.audit('import', str(zip_path))
        return results

