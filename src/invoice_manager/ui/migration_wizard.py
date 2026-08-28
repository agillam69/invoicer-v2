"""Simple wizard for importing legacy v1 CSV data."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.application.migration_service import MigrationService
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.infrastructure.file_store import FileStore
from invoice_manager.persistence.database import Database
from invoice_manager.persistence.repositories import (
    ClientRepository,
    InvoiceRepository,
    LedgerRepository,
    MigrationIssueRepository,
    PaymentRepository,
    ServiceItemRepository,
    SettingRepository,
)


class MigrationWizard(QDialog):
    """Dialog to select a v1 data folder and import it into v2."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Import legacy data")
        self.setMinimumSize(600, 400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Select the folder containing the old v1 CSVs (clients.csv, invoices.csv, etc.)."
            )
        )

        path_layout = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setPlaceholderText("C:/Users/.../Invoicer")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_layout.addWidget(self._path)
        path_layout.addWidget(browse)
        layout.addLayout(path_layout)

        form = QFormLayout()
        self._terms = QLineEdit("7")
        form.addRow("Default payment terms (days):", self._terms)
        layout.addLayout(form)

        run = QPushButton("Run import")
        run.clicked.connect(self._run)
        layout.addWidget(run)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select legacy data folder")
        if path:
            self._path.setText(path)

    def _run(self) -> None:
        source = Path(self._path.text().strip())
        if not source.exists():
            QMessageBox.warning(self, "Folder not found", f"{source} does not exist.")
            return
        try:
            db = Database(self._config.db_path())
            db.create_schema()
            session = db.new_session()
            file_store = FileStore(self._config.get_data_directory())
            setting_repo = SettingRepository(session)
            service = MigrationService(
                source_dir=source,
                setting_repo=setting_repo,
                client_repo=ClientRepository(session),
                service_repo=ServiceItemRepository(session),
                invoice_repo=InvoiceRepository(session),
                payment_repo=PaymentRepository(session),
                ledger_repo=LedgerRepository(session),
                issue_repo=MigrationIssueRepository(session),
                file_store=file_store,
                payment_terms_days=int(self._terms.text() or 7),
            )
            counts = service.run()
            setting_repo.set("migration_source_dir", str(source))
            session.commit()
            self._log.appendPlainText(f"Imported: {counts}")
            self._log.appendPlainText(f"Issues: {service._issue_count}")
        except Exception as exc:  # noqa: BLE001
            self._log.appendPlainText(f"ERROR: {exc}")
            QMessageBox.critical(self, "Import failed", str(exc))
        finally:
            session.close()
            db.engine.dispose()
