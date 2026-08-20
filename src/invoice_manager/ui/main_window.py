from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

DESTINATIONS = (
    "Dashboard",
    "New Invoice",
    "Invoices",
    "Payments & Receipts",
    "Clients",
    "Products & Services",
    "Income & Expenses",
    "Reports",
)


class MainWindow(QMainWindow):
    def __init__(self, user_display_name: str = "") -> None:
        super().__init__()
        self.setWindowTitle("Invoicer V2")
        self.resize(1100, 720)
        self.nav = QListWidget()
        self.nav.setObjectName("navigationRail")
        self.nav.setFixedWidth(210)
        for destination in DESTINATIONS:
            QListWidgetItem(destination, self.nav)
        self.pages = QStackedWidget()
        for destination in DESTINATIONS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            title = QLabel(destination)
            title.setStyleSheet("font-size: 24px; font-weight: 600;")
            page_layout.addWidget(title)
            if destination == "Dashboard":
                text = "Your financial dashboard will arrive in a later phase."
            else:
                text = f"{destination} will arrive in a later phase."
            empty = QLabel(text)
            empty.setWordWrap(True)
            page_layout.addWidget(empty)
            page_layout.addStretch()
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.addWidget(self.nav)
        central_layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self._build_menu()
        self.statusBar().showMessage(f"Signed in: {user_display_name}" if user_display_name else "")

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Application")
        for label in (
            "Settings",
            "Import/Migrate",
            "Export",
            "Backup Now",
            "Restore",
            "Users",
            "Audit Log",
            "App Log",
            "Help",
            "About",
        ):
            action = menu.addAction(label)
            action.setEnabled(False)
            action.setToolTip("Available in a later phase")
