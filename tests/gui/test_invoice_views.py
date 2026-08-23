from datetime import date

import pytest

from invoice_manager.application.client_service import ClientService
from invoice_manager.application.invoice_service import InvoiceItemData, InvoiceService
from invoice_manager.ui.invoice_editor import InvoiceEditorView
from invoice_manager.ui.invoice_list import InvoiceListView


@pytest.mark.gui
def test_editor_line_totals_and_save_reload(qtbot, session) -> None:
    client = ClientService().create(session, display_name="GUI Client")
    editor = InvoiceEditorView(session)
    qtbot.addWidget(editor)
    editor.client_combo.setCurrentIndex(editor.client_combo.findData(client.id))
    editor.description_input.setText("Design")
    editor.quantity_input.setText("2")
    editor.price_input.setText("1250")
    editor.add_line_button.click()
    assert editor.subtotal_label.text() == "$25.00"
    assert editor.total_label.text() == "$25.00"
    editor._save()
    assert editor.invoice is not None
    invoice_id = editor.invoice.id
    reloaded = InvoiceEditorView(session, session.get(type(editor.invoice), invoice_id))
    qtbot.addWidget(reloaded)
    assert reloaded.lines_table.rowCount() == 1
    assert reloaded.total_label.text() == "$25.00"


@pytest.mark.gui
def test_editor_issue_assigns_one_number(qtbot, session, monkeypatch) -> None:
    client = ClientService().create(session, display_name="Issue GUI")
    editor = InvoiceEditorView(session)
    qtbot.addWidget(editor)
    editor.client_combo.setCurrentIndex(editor.client_combo.findData(client.id))
    editor.description_input.setText("Work")
    editor.price_input.setText("100")
    editor.add_line_button.click()
    editor._save()
    monkeypatch.setattr(
        "invoice_manager.ui.invoice_editor.QMessageBox.question",
        lambda *args: 16384,
    )
    editor._issue()
    assert editor.invoice is not None
    assert editor.invoice.canonical_number == "INV-0001"


@pytest.mark.gui
def test_invoice_list_search_and_export(qtbot, session) -> None:
    client = ClientService().create(session, display_name="Searchable")
    InvoiceService().create_draft(
        session,
        client,
        [InvoiceItemData("Listed", 1, 100)],
        invoice_date=date(2026, 1, 1),
    )
    view = InvoiceListView(session)
    qtbot.addWidget(view)
    assert view.table.rowCount() == 1
    view.search.setText("Searchable")
    assert view.table.rowCount() == 1
    view.search.setText("missing")
    assert view.table.rowCount() == 0
    assert "canonical_number" in view.service.export_csv(session)
