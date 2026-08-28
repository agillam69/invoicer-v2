"""Placeholder page used until a navigation section is implemented."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    """States plainly which phase delivers the section, instead of a fake UI."""

    def __init__(self, title: str, phase: str, summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"page_{title.lower().replace(' ', '_').replace('&', 'and')}")

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")

        detail = QLabel(f"{summary}\n\nThis section is delivered in {phase}.")
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(detail)
        layout.addStretch(1)
