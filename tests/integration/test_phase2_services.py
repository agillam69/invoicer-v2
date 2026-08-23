from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from invoice_manager.application.client_service import ClientService
from invoice_manager.application.invoice_service import InvoiceItemData, InvoiceService
from invoice_manager.application.service_item_service import ServiceItemService
from invoice_manager.persistence.models import (
    AuditEvent,
    BusinessProfile,
    CreditNoteItem,
    Invoice,
)


def test_clients_services_and_invoice_snapshots(session) -> None:
    clients = ClientService()
    services = ServiceItemService()
    invoices = InvoiceService()
    client = clients.create(session, display_name="Snapshot Client", email="a@example.com")
    item = services.create(
        session, code="WEB", name="Website", unit_price_cents=10000, taxable=True
    )
    business = BusinessProfile(
        business_name="Alex Gillam",
        abn="12345678901",
        email="business@example.com",
        gst_registered=True,
        gst_rate=Decimal("10"),
    )
    session.add(business)
    session.flush()
    draft = invoices.create_draft(
        session,
        client,
        [
            InvoiceItemData(
                description=item.name,
                quantity=2,
                unit_price_cents=item.unit_price_cents,
                service_item_id=item.id,
                service_code=item.code,
                taxable=item.taxable,
                gst_rate=business.gst_rate,
            ),
            InvoiceItemData(description="Custom", quantity=1, unit_price_cents=500, taxable=False),
        ],
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 15),
        business=business,
    )
    assert draft.total_cents == 22500
    invoices.issue(session, draft)
    session.commit()
    client.display_name = "Changed client"
    item.name = "Changed service"
    session.commit()
    session.refresh(draft)
    assert draft.client_name_snapshot == "Snapshot Client"
    assert draft.items[0].description == "Website"
    with pytest.raises(ValueError, match="immutable"):
        invoices.save_draft(session, draft, client, [])


def test_client_duplicate_merge_delete_and_rollup(session) -> None:
    service = ClientService()
    first = service.create(session, display_name="Same Person", email="same@example.com")
    with pytest.raises(ValueError, match="duplicate"):
        service.create(session, display_name="Same Person", email="same@example.com")
    second = service.create(session, display_name="Replacement")
    invoice = Invoice(
        invoice_date=date(2026, 1, 1),
        due_date=date.today() - timedelta(days=1),
        client_id=first.id,
        total_cents=100,
        subtotal_cents=100,
        client_name_snapshot=first.display_name,
    )
    session.add(invoice)
    session.flush()
    service.merge(session, first, second)
    assert invoice.client_id == second.id
    assert first.active is False
    assert service.rollup(session, second)["billed_cents"] == 100
    with pytest.raises(ValueError, match="referenced"):
        service.delete(session, second)
    assert session.scalar(select(AuditEvent).where(AuditEvent.entity_type == "client")) is not None


def test_invoice_corrections_and_registration(session) -> None:
    clients = ClientService()
    invoices = InvoiceService()
    client = clients.create(session, display_name="Corrections")
    external = invoices.register_external(session, client, "EXT-10", date(2026, 1, 1), 500)
    with pytest.raises(ValueError, match="already exists"):
        invoices.register_external(session, client, "EXT-10", date(2026, 1, 1), 500)
    invoices.cancel(session, external, "Entered in error")
    assert invoices.status(session, external).value == "Cancelled"
    note = invoices.create_credit_note(
        session,
        external,
        [InvoiceItemData(description="Correction", quantity=1, unit_price_cents=100)],
        "Refund",
    )
    assert note.total_cents == 100
    assert (
        session.scalar(select(CreditNoteItem).where(CreditNoteItem.credit_note_id == note.id))
        is not None
    )
