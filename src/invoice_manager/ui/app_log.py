from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class AppLogDialog(QDialog):
    LEVELS = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    def __init__(self, log_path: Path) -> None:
        super().__init__()
        self.log_path = log_path
        self.setWindowTitle("Invoicer V2 — App Log")
        self.level = QComboBox()
        self.level.addItems(self.LEVELS)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search log")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Level"))
        controls.addWidget(self.level)
        controls.addWidget(self.search, 1)
        controls.addWidget(refresh)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.output)
        self.level.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        lines: list[str] = []
        for path in sorted(self.log_path.parent.glob("app.log*"), reverse=True):
            if path.is_file():
                lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
        selected_level = self.level.currentText()
        search = self.search.text().casefold()
        self.output.setPlainText(
            "\n".join(
                line
                for line in lines
                if (selected_level == "ALL" or f" {selected_level} " in line)
                and (not search or search in line.casefold())
            )
        )
