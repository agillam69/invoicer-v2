"""Settings and numbering configuration dialog."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
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
        form = QFormLayout()

        for key in self._STRING_KEYS:
            edit = QLineEdit()
            form.addRow(self._label(key), edit)
            self._fields[key] = edit

        self._gst_rate = QLineEdit()
        form.addRow("GST rate (e.g. 0.10):", self._gst_rate)

        self._payment_terms = QSpinBox()
        self._payment_terms.setRange(0, 365)
        form.addRow("Payment terms (days):", self._payment_terms)

        self._next_invoice = QSpinBox()
        self._next_invoice.setRange(1, 999999)
        form.addRow("Next invoice number:", self._next_invoice)

        self._next_receipt = QSpinBox()
        self._next_receipt.setRange(1, 999999)
        form.addRow("Next receipt number:", self._next_receipt)

        layout.addLayout(form)

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

        self._context.session.commit()
        QMessageBox.information(self, "Saved", "Settings saved.")
        self.accept()
