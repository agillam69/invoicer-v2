from datetime import date

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from invoice_manager.persistence.models import Client, Invoice, InvoiceItem, Payment


def test_foreign_keys_enabled_and_orphans_rejected(session) -> None:
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    session.add(Payment(invoice_id=999, amount_cents=100, payment_date=date.today()))
    with pytest.raises(IntegrityError):
        session.commit()


def test_non_negative_and_enumerated_checks(session) -> None:
    session.add(Client(display_name="Client"))
    session.flush()
    session.add(Invoice(invoice_date=date.today(), due_date=date.today(),
                        client_id=1, total_cents=-1))
    with pytest.raises(IntegrityError):
        session.commit()
