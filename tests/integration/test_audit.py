from invoice_manager.infrastructure.audit import AuditService


def test_audit_record(audit_repo):
    service = AuditService(audit_repo, current_user="admin")
    service.record(
        action="invoice_issued",
        table_name="invoices",
        record_id=1,
        detail={"number": "INV-0001"},
    )
    recent = audit_repo.list_recent()
    assert len(recent) == 1
    assert recent[0].action == "invoice_issued"
    assert recent[0].user == "admin"
    assert '"number": "INV-0001"' in recent[0].detail


def test_audit_string_detail(audit_repo):
    service = AuditService(audit_repo, current_user="system")
    service.record(action="login", detail="user logged in")
    recent = audit_repo.list_recent()
    assert recent[0].detail == "user logged in"
