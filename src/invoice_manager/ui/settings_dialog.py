"""Settings and numbering configuration dialog."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.ui.app_context import AppContext


class SettingsDialog(QDialog):
    """Edit business settings and document numbering."""

    _STRING_KEYS = [
        "business_name",
        "business_address",
        "business_abn",
        "business_phone",
        "business_email",
        "currency_symbol",
        "bank_name",
        "bank_bsb",
        "bank_account",
        "bank_account_name",
        "thank_you_note",
    ]

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._fields: dict[str, QLineEdit] = {}
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setMinimumWidth(550)

        tabs = QTabWidget()

        # Business tab
        biz_group = QGroupBox("Business")
        biz_form = QFormLayout()
        for key in self._STRING_KEYS:
            edit = QLineEdit()
            biz_form.addRow(self._label(key), edit)
            self._fields[key] = edit
        self._gst_rate = QLineEdit()
        biz_form.addRow("GST rate (e.g. 0.10):", self._gst_rate)
        self._payment_terms = QSpinBox()
        self._payment_terms.setRange(0, 365)
        biz_form.addRow("Payment terms (days):", self._payment_terms)
        self._next_invoice = QSpinBox()
        self._next_invoice.setRange(1, 999999)
        biz_form.addRow("Next invoice number:", self._next_invoice)
        self._next_receipt = QSpinBox()
        self._next_receipt.setRange(1, 999999)
        biz_form.addRow("Next receipt number:", self._next_receipt)
        biz_group.setLayout(biz_form)
        tabs.addTab(biz_group, "Business")

        # Reports / PDF tab
        report_group = QGroupBox("Reports & PDF")
        report_form = QFormLayout()
        self._report_header_colour = QLineEdit()
        report_form.addRow("Report header colour (hex):", self._report_header_colour)
        self._report_accent_colour = QLineEdit()
        report_form.addRow("Report accent colour (hex):", self._report_accent_colour)
        self._report_stripe_colour = QLineEdit()
        report_form.addRow("Report stripe colour (hex):", self._report_stripe_colour)
        self._report_footer = QLineEdit()
        report_form.addRow("Report footer:", self._report_footer)
        self._pdf_save_mode = QComboBox()
        self._pdf_save_mode.addItems(["Auto", "Prompt"])
        report_form.addRow("PDF save mode:", self._pdf_save_mode)
        report_group.setLayout(report_form)
        tabs.addTab(report_group, "Reports")

        # Backup tab
        backup_group = QGroupBox("Backup")
        backup_form = QFormLayout()
        self._backup_enabled = QCheckBox("Enable scheduled backups")
        backup_form.addRow(self._backup_enabled)
        self._backup_frequency = QSpinBox()
        self._backup_frequency.setRange(1, 168)
        backup_form.addRow("Frequency (hours):", self._backup_frequency)
        self._backup_keep = QSpinBox()
        self._backup_keep.setRange(1, 365)
        backup_form.addRow("Keep count:", self._backup_keep)
        self._backup_on_exit = QCheckBox("Backup on exit")
        backup_form.addRow(self._backup_on_exit)
        self._backup_folder = QLineEdit()
        backup_browse = QPushButton("Browse...")
        backup_browse.clicked.connect(self._browse_backup_folder)
        backup_row = QHBoxLayout()
        backup_row.addWidget(self._backup_folder)
        backup_row.addWidget(backup_browse)
        backup_form.addRow("Backup folder:", backup_row)
        backup_group.setLayout(backup_form)
        tabs.addTab(backup_group, "Backup")

        # Data / Setup tab
        data_group = QGroupBox("Data & Setup")
        data_form = QFormLayout()

        self._data_dir = QLineEdit()
        self._data_dir.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_data_dir)
        onedrive_btn = QPushButton("Use OneDrive")
        onedrive_btn.clicked.connect(self._use_onedrive)
        data_row = QHBoxLayout()
        data_row.addWidget(self._data_dir)
        data_row.addWidget(browse_btn)
        data_row.addWidget(onedrive_btn)
        data_form.addRow("Data folder:", data_row)

        self._database_path = QLineEdit()
        self._database_path.setReadOnly(True)
        open_db_btn = QPushButton("Open database location")
        open_db_btn.clicked.connect(self._open_database_location)
        db_row = QHBoxLayout()
        db_row.addWidget(self._database_path)
        db_row.addWidget(open_db_btn)
        data_form.addRow("Database file:", db_row)

        self._migration_source = QLineEdit()
        self._migration_source.setReadOnly(True)
        open_source_btn = QPushButton("Open source folder")
        open_source_btn.clicked.connect(self._open_migration_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self._migration_source)
        source_row.addWidget(open_source_btn)
        data_form.addRow("Migration / CSV source:", source_row)

        data_form.addRow(QLabel("Changing data folders requires a restart to take effect."))
        data_group.setLayout(data_form)
        tabs.addTab(data_group, "Data")

        layout.addWidget(tabs)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _label(self, key: str) -> str:
        return " ".join(part.capitalize() for part in key.replace("_", " ").split())

    def _load(self) -> None:
        settings = self._context.setting_repo
        for key, edit in self._fields.items():
            edit.setText(settings.get(key) or "")
        self._gst_rate.setText(settings.get("gst_rate") or "0.0")
        self._payment_terms.setValue(settings.get_int("payment_terms_days", 7))
        self._next_invoice.setValue(settings.get_int("next_invoice_number", 1))
        self._next_receipt.setValue(settings.get_int("next_receipt_number", 1))

        self._report_header_colour.setText(settings.get("report_header_colour") or "#2C3E50")
        self._report_accent_colour.setText(settings.get("report_accent_colour") or "#2980B9")
        self._report_stripe_colour.setText(settings.get("report_stripe_colour") or "#EBF5FB")
        self._report_footer.setText(settings.get("report_footer") or "")
        pdf_mode = settings.get("pdf_save_mode") or "Auto"
        self._pdf_save_mode.setCurrentText(pdf_mode if pdf_mode in ("Auto", "Prompt") else "Auto")

        self._backup_enabled.setChecked(settings.get("backup_enabled") == "1")
        self._backup_frequency.setValue(settings.get_int("backup_frequency_hours", 24))
        self._backup_keep.setValue(settings.get_int("backup_keep", 30))
        self._backup_on_exit.setChecked(settings.get("backup_on_exit") == "1")
        self._backup_folder.setText(settings.get("backup_folder") or "")

        self._data_dir.setText(str(self._context.config.get_data_directory()))
        self._database_path.setText(str(self._context.config.db_path()))
        self._migration_source.setText(settings.get("migration_source_dir") or "")

    def _save(self) -> None:
        settings = self._context.setting_repo
        for key, edit in self._fields.items():
            settings.set(key, edit.text().strip())

        gst = self._gst_rate.text().strip() or "0.0"
        try:
            Decimal(gst)
        except Exception:
            QMessageBox.warning(self, "Invalid", "GST rate must be a valid decimal.")
            return
        settings.set("gst_rate", gst)
        settings.set("payment_terms_days", str(self._payment_terms.value()))

        self._context.invoice_service.set_next_invoice_number(self._next_invoice.value())
        self._context.payment_service.set_next_receipt_number(self._next_receipt.value())

        # Also store the number settings in case services have not flushed yet.
        settings.set("next_invoice_number", str(self._next_invoice.value()))
        settings.set("next_receipt_number", str(self._next_receipt.value()))

        settings.set("report_header_colour", self._report_header_colour.text().strip())
        settings.set("report_accent_colour", self._report_accent_colour.text().strip())
        settings.set("report_stripe_colour", self._report_stripe_colour.text().strip())
        settings.set("report_footer", self._report_footer.text().strip())
        settings.set("pdf_save_mode", self._pdf_save_mode.currentText())

        settings.set("backup_enabled", "1" if self._backup_enabled.isChecked() else "0")
        settings.set("backup_frequency_hours", str(self._backup_frequency.value()))
        settings.set("backup_keep", str(self._backup_keep.value()))
        settings.set("backup_on_exit", "1" if self._backup_on_exit.isChecked() else "0")
        settings.set("backup_folder", self._backup_folder.text().strip())

        new_data_dir = Path(self._data_dir.text())
        if new_data_dir != self._context.config.get_data_directory():
            self._context.config.set_data_directory(new_data_dir)

        self._context.session.commit()
        QMessageBox.information(self, "Saved", "Settings saved.")
        self.accept()

    def _browse_data_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select data directory", self._data_dir.text()
        )
        if path:
            self._data_dir.setText(path)

    def _use_onedrive(self) -> None:
        onedrive = os.environ.get("ONEDRIVE") or str(Path.home() / "OneDrive")
        target = Path(onedrive) / "InvoiceReceiptManager"
        self._data_dir.setText(str(target))

    def _browse_backup_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select backup folder", self._backup_folder.text() or self._data_dir.text()
        )
        if path:
            self._backup_folder.setText(path)

    def _open_database_location(self) -> None:
        path = Path(self._database_path.text())
        if not path.exists():
            QMessageBox.warning(self, "Not found", f"Database file not found: {path}")
            return
        os.startfile(str(path.parent))

    def _open_migration_source(self) -> None:
        source = self._migration_source.text().strip()
        if not source:
            QMessageBox.information(self, "No source", "No migration source is recorded.")
            return
        path = Path(source)
        if not path.exists():
            QMessageBox.warning(self, "Not found", f"Source folder not found: {path}")
            return
        os.startfile(str(path))
