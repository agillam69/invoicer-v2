"""Main application window with a left navigation rail."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.application.backup_service import BackupService, BackupServiceError
from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.infrastructure.logging_setup import get_logger
from invoice_manager.ui.app_context import AppContext
from invoice_manager.ui.clients_page import ClientsPage
from invoice_manager.ui.dashboard_page import DashboardPage
from invoice_manager.ui.invoice_editor import InvoiceEditorDialog
from invoice_manager.ui.invoice_list import InvoiceListPage
from invoice_manager.ui.ledger_page import LedgerPage
from invoice_manager.ui.migration_wizard import MigrationWizard
from invoice_manager.ui.payments_page import PaymentsPage
from invoice_manager.ui.reports_page import ReportsPage
from invoice_manager.ui.service_items_page import ServiceItemsPage
from invoice_manager.ui.settings_dialog import SettingsDialog

_log = get_logger("invoice_manager.ui.main_window")

_NAV_ITEMS = [
    "Dashboard",
    "New Invoice",
    "Invoices",
    "Payments & Receipts",
    "Clients",
    "Products & Services",
    "Income & Expenses",
    "Reports",
]


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, current_user: str) -> None:
        super().__init__()
        self._config = config
        self._current_user = current_user
        self._context = AppContext(config, current_user)
        self.setWindowTitle("Invoice & Receipt Manager")
        self.setMinimumSize(1200, 800)
        self._build_ui()
        self._start_backup_scheduler()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left nav rail
        nav_container = QWidget()
        nav_container.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 8, 8, 8)

        self._nav = QListWidget()
        for label in _NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._nav.addItem(item)
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        nav_layout.addWidget(self._nav)

        self._status_label = QLabel(f"User: {self._current_user}")
        self._status_label.setWordWrap(True)
        nav_layout.addWidget(self._status_label)

        layout.addWidget(nav_container)

        # Content area
        self._stack = QStackedWidget()
        self._pages: list[QWidget] = []
        for label in _NAV_ITEMS:
            page = self._create_page(label)
            self._pages.append(page)
            self._stack.addWidget(page)
        layout.addWidget(self._stack, stretch=1)

        self._build_menu()

    def _create_page(self, label: str) -> QWidget:
        if label == "Dashboard":
            return DashboardPage(self._context)
        if label == "Invoices":
            return InvoiceListPage(self._context)
        if label == "Payments & Receipts":
            return PaymentsPage(self._context)
        if label == "Clients":
            return ClientsPage(self._context)
        if label == "Products & Services":
            return ServiceItemsPage(self._context)
        if label == "Income & Expenses":
            return LedgerPage(self._context)
        if label == "Reports":
            return ReportsPage(self._context)
        return self._placeholder_page(label)

    def _placeholder_page(self, label: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"<h1>{label}</h1><p>This screen is under construction.</p>"))
        layout.addStretch()
        return page

    def _on_nav_changed(self, index: int) -> None:
        label = _NAV_ITEMS[index]
        if label == "New Invoice":
            self._open_new_invoice()
            self._nav.setCurrentRow(2)
            return
        self._stack.setCurrentIndex(index)
        page = self._pages[index]
        if hasattr(page, "refresh"):
            page.refresh()

    def _build_menu(self) -> None:
        menu_bar = QMenuBar(self)
        tools_menu = menu_bar.addMenu("Tools")
        import_action = tools_menu.addAction("Import / Migrate")
        import_action.triggered.connect(self._open_migration_wizard)
        backup_action = tools_menu.addAction("Backup now")
        backup_action.triggered.connect(self._backup_now)
        restore_action = tools_menu.addAction("Restore from backup...")
        restore_action.triggered.connect(self._restore_backup)
        tools_menu.addSeparator()
        settings_action = tools_menu.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)
        self.setMenuBar(menu_bar)

    def _open_migration_wizard(self) -> None:
        wizard = MigrationWizard(self._config, parent=self)
        wizard.exec()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._context, parent=self)
        dlg.exec()

    def _open_new_invoice(self) -> None:
        dlg = InvoiceEditorDialog(self._context, parent=self)
        if dlg.exec() == 1:
            invoices_page = self._pages[2]
            if isinstance(invoices_page, InvoiceListPage):
                invoices_page.refresh()

    def _start_backup_scheduler(self) -> None:
        self._backup_if_due()
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._backup_if_due)
        self._backup_timer.start(15 * 60 * 1000)

    def _backup_if_due(self) -> None:
        try:
            service = BackupService(
                self._context.config.get_data_directory(),
                self._context.config.get_backup_directory(),
                self._context.setting_repo,
            )
            if service.backup_if_due():
                _log.info("Scheduled backup completed")
        except Exception:  # noqa: BLE001
            _log.exception("Scheduled backup failed")

    def _backup_on_exit(self) -> None:
        try:
            service = BackupService(
                self._context.config.get_data_directory(),
                self._context.config.get_backup_directory(),
                self._context.setting_repo,
            )
            if service.backup_on_exit():
                _log.info("Exit backup completed")
        except Exception:  # noqa: BLE001
            _log.exception("Exit backup failed")

    def _backup_now(self) -> None:
        try:
            service = BackupService(
                self._context.config.get_data_directory(),
                self._context.config.get_backup_directory(),
                self._context.setting_repo,
            )
            path = service.backup()
            service.prune()
            QMessageBox.information(self, "Backup complete", f"Saved: {path}")
        except BackupServiceError as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def _restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select backup zip",
            str(self._context.config.get_backup_directory()),
            "Zip files (*.zip)",
        )
        if not path:
            return
        reply = QMessageBox.question(
            self,
            "Confirm restore",
            "This will overwrite the current data with the backup.\nA safety copy will be made first. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            service = BackupService(
                self._context.config.get_data_directory(),
                self._context.config.get_backup_directory(),
            )
            service.restore(Path(path))
            QMessageBox.information(self, "Restore complete", "Please restart the application.")
        except BackupServiceError as exc:
            QMessageBox.critical(self, "Restore failed", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._backup_on_exit()
        self._context.session.close()
        self._context.database.engine.dispose()
        event.accept()
