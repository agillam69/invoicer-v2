"""Application shell: left navigation rail, application menu and status bar."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from invoice_manager import __version__
from invoice_manager.application.auth_service import AuthenticatedUser
from invoice_manager.config import AppPaths
from invoice_manager.ui.common.placeholder import PlaceholderPage

NAV_RAIL_WIDTH = 210


@dataclass(frozen=True, slots=True)
class NavSection:
    title: str
    phase: str
    summary: str


NAV_SECTIONS: tuple[NavSection, ...] = (
    NavSection(
        "Dashboard",
        "Phase 5",
        "Financial-year cards, recent invoices and payments, and data issues needing attention.",
    ),
    NavSection(
        "New Invoice",
        "Phase 3",
        "Compact invoice header, line-item editor with live totals, and Issue Invoice.",
    ),
    NavSection(
        "Invoices",
        "Phase 3",
        "Searchable invoice history with status colours and record-level actions.",
    ),
    NavSection(
        "Payments & Receipts",
        "Phase 4",
        "Multiple and partial payments, reversals, and receipts generated from saved payments.",
    ),
    NavSection("Clients", "Phase 2", "Client records, duplicate detection, merge and totals."),
    NavSection(
        "Products & Services", "Phase 3", "Reusable service catalogue with defaults and pricing."
    ),
    NavSection(
        "Income & Expenses",
        "Phase 5",
        "Manual non-invoice income and expenses with categories and evidence.",
    ),
    NavSection(
        "Reports",
        "Phase 5",
        "Registers, ageing, client statements, profit and loss, and GST by financial year.",
    ),
)

MENU_ITEMS: dict[str, tuple[str, ...]] = {
    "&Application": ("Settings", "Import/Migrate", "Export", "Backup Now", "Restore"),
    "&Users": ("Users",),
    "&Logs": ("Audit Log", "App Log"),
    "&Help": ("Help", "About"),
}

PENDING_PHASES: dict[str, str] = {
    "Settings": "Phase 3",
    "Import/Migrate": "Phase 2",
    "Export": "Phase 5",
    "Backup Now": "Phase 6",
    "Restore": "Phase 6",
    "Users": "Phase 1",
    "Audit Log": "Phase 6",
    "App Log": "Phase 6",
    "Help": "Phase 6",
}


class MainWindow(QMainWindow):
    """Shell that hosts each navigation section as a stacked page."""

    def __init__(
        self, user: AuthenticatedUser, paths: AppPaths, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._user = user
        self._paths = paths

        self.setWindowTitle("Invoicer V2")
        self.resize(QSize(1280, 800))

        self._nav = QListWidget()
        self._nav.setFixedWidth(NAV_RAIL_WIDTH)
        self._nav.setObjectName("navigationRail")
        self._pages = QStackedWidget()

        for index, section in enumerate(NAV_SECTIONS, start=1):
            item = QListWidgetItem(f"{index}. {section.title}")
            item.setData(Qt.ItemDataRole.UserRole, section.title)
            self._nav.addItem(item)
            self._pages.addWidget(PlaceholderPage(section.title, section.phase, section.summary))

        self._nav.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._nav.setCurrentRow(0)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._nav)
        layout.addWidget(self._pages, 1)
        self.setCentralWidget(central)

        self._build_menus()
        self._build_status_bar()

    def _build_menus(self) -> None:
        for menu_title, entries in MENU_ITEMS.items():
            menu = self.menuBar().addMenu(menu_title)
            for entry in entries:
                action = menu.addAction(entry)
                if entry == "About":
                    action.triggered.connect(self._show_about)
                else:
                    action.triggered.connect(
                        lambda _checked=False, name=entry: self._show_pending(name)
                    )

    def _build_status_bar(self) -> None:
        user_label = QLabel(f"User: {self._user.display_name} ({self._user.username})")
        data_label = QLabel(f"Data: {self._paths.root}")
        data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.statusBar().addWidget(user_label)
        self.statusBar().addPermanentWidget(data_label)

    def _show_pending(self, name: str) -> None:
        phase = PENDING_PHASES.get(name, "a later phase")
        QMessageBox.information(self, name, f"{name} is delivered in {phase}.")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Invoicer V2",
            f"Invoicer V2 {__version__}\n"
            "Local invoice, receipt, payment and reporting manager.\n"
            f"Data location: {self._paths.root}",
        )

    def select_section(self, index: int) -> None:
        self._nav.setCurrentRow(index)

    def current_section_title(self) -> str:
        item = self._nav.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
