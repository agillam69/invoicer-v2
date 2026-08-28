"""Main application window with a left navigation rail."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenuBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.infrastructure.config import AppConfig
from invoice_manager.infrastructure.logging_setup import get_logger
from invoice_manager.ui.app_context import AppContext
from invoice_manager.ui.invoice_list import InvoiceListPage
from invoice_manager.ui.ledger_page import LedgerPage
from invoice_manager.ui.migration_wizard import MigrationWizard

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
        if label == "Invoices":
            return InvoiceListPage(self._context)
        if label == "Income & Expenses":
            return LedgerPage(self._context)
        return self._placeholder_page(label)

    def _placeholder_page(self, label: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"<h1>{label}</h1><p>This screen is under construction.</p>"))
        layout.addStretch()
        return page

    def _on_nav_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        page = self._pages[index]
        if hasattr(page, "refresh"):
            page.refresh()

    def _build_menu(self) -> None:
        menu_bar = QMenuBar(self)
        tools_menu = menu_bar.addMenu("Tools")
        import_action = tools_menu.addAction("Import / Migrate")
        import_action.triggered.connect(self._open_migration_wizard)
        self.setMenuBar(menu_bar)

    def _open_migration_wizard(self) -> None:
        wizard = MigrationWizard(self._config, parent=self)
        wizard.exec()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._context.session.close()
        self._context.database.engine.dispose()
        event.accept()
