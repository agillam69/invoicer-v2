"""Products & Services management page."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from invoice_manager.domain.invoices import STANDARD_UNITS
from invoice_manager.persistence.models import ServiceItem
from invoice_manager.ui.app_context import AppContext


class ServiceItemDialog(QDialog):
    """Add or edit a product/service item."""

    def __init__(
        self,
        context: AppContext,
        item: ServiceItem | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._item = item
        self.setWindowTitle("Edit Service Item" if item else "Add Service Item")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._description = QLineEdit()
        form.addRow("Description:", self._description)

        self._unit = QComboBox()
        self._unit.setEditable(True)
        self._unit.addItems(list(STANDARD_UNITS))
        self._unit.setCurrentText("ea")
        form.addRow("Unit:", self._unit)

        self._price = QDoubleSpinBox()
        self._price.setMaximum(9999999.99)
        self._price.setMinimum(0)
        self._price.setDecimals(2)
        form.addRow("Unit price ($):", self._price)

        self._taxable = QCheckBox("Taxable")
        self._taxable.setChecked(self._context.setting_repo.get("default_taxable") == "1")
        form.addRow(self._taxable)

        layout.addLayout(form)

        if self._item is not None:
            self._description.setText(self._item.description)
            self._unit.setCurrentText(self._item.unit or "ea")
            self._price.setValue(self._item.unit_price_cents / 100)
            self._taxable.setChecked(self._item.taxable)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _save(self) -> None:
        description = self._description.text().strip()
        if not description:
            QMessageBox.warning(self, "Missing description", "Description is required.")
            return
        unit = self._unit.currentText().strip()
        if not unit:
            QMessageBox.warning(self, "Missing unit", "Select or enter a unit.")
            return
        price_cents = int(round(self._price.value() * 100))
        if self._item is None:
            self._context.service_repo.create(
                description=description,
                unit_price_cents=price_cents,
                taxable=self._taxable.isChecked(),
                unit=unit,
            )
        else:
            self._item.description = description
            self._item.unit_price_cents = price_cents
            self._item.unit = unit
            self._item.taxable = self._taxable.isChecked()
        self._context.session.commit()
        self.accept()


class ServiceItemsPage(QWidget):
    """Page for listing and managing products and services."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._items: list[ServiceItem] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Products & Services"))

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add item")
        add_btn.clicked.connect(self._add_item)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Description", "Unit", "Price", "Taxable"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit_item)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._table)

        action_bar = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_item)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_item)
        action_bar.addWidget(edit_btn)
        action_bar.addWidget(delete_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def refresh(self) -> None:
        self._items = self._context.service_repo.list_active()
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self._table.setItem(row, 0, QTableWidgetItem(item.description))
            self._table.setItem(row, 1, QTableWidgetItem(item.unit or ""))
            self._table.setItem(row, 2, QTableWidgetItem(f"${item.unit_price_cents / 100:.2f}"))
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if item.taxable else Qt.CheckState.Unchecked)
            self._table.setItem(row, 3, chk)

    def _selected_item(self) -> ServiceItem | None:
        rows = self._table.selectedIndexes()
        if not rows:
            return None
        return self._items[rows[0].row()]

    def _add_item(self) -> None:
        dlg = ServiceItemDialog(self._context, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _edit_item(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, "Select item", "Select an item to edit.")
            return
        dlg = ServiceItemDialog(self._context, item=item, parent=self)
        if dlg.exec() == 1:
            self.refresh()

    def _delete_item(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, "Select item", "Select an item to delete.")
            return
        reply = QMessageBox.question(
            self,
            "Confirm delete",
            f"Delete service item '{item.description}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        reason, ok = QInputDialog.getText(
            self, "Delete reason (optional)", "Reason for deleting service item:"
        )
        if not ok:
            return
        item.is_deleted = True
        self._context.session.commit()
        self._context.audit.record(
            "service_item_deleted", "service_items", item.id, {"reason": reason.strip() or None}
        )
        self.refresh()

    def _context_menu(self, pos: QPoint) -> None:
        item = self._selected_item()
        if item is None:
            return
        menu = QMenu(self)
        menu.addAction("Add item", self._add_item)
        menu.addAction("Edit item", self._edit_item)
        menu.addAction("Delete item", self._delete_item)
        menu.exec(self._table.viewport().mapToGlobal(pos))
