from sqlalchemy import select

from invoice_manager.application.audit import AuditService
from invoice_manager.persistence.models import AuditEvent, Client


def test_audit_and_business_action_share_transaction(session) -> None:
    client = Client(display_name="Audited Client")
    session.add(client)
    session.flush()
    AuditService().record(session, action="create", entity_type="client",
                          entity_id=client.id, summary="Created client")
    session.commit()
    assert session.scalar(select(AuditEvent).where(AuditEvent.entity_id == client.id)) is not None
    second = Client(display_name="Rolled back")
    session.add(second)
    session.flush()
    AuditService().record(session, action="create", entity_type="client",
                          entity_id=second.id, summary="Rolled back client")
    session.rollback()
    assert session.get(Client, second.id) is None
    assert session.scalar(select(AuditEvent).where(AuditEvent.entity_id == second.id)) is None
