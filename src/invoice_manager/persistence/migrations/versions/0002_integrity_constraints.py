"""Enforce issued-invoice numbering, payment reversal reasons and document locations."""

from alembic import op

revision = "0002_integrity_constraints"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

CONSTRAINTS = (
    ("invoices", "ck_invoice_issued_number", "issued_at IS NULL OR canonical_number IS NOT NULL"),
    (
        "payments",
        "ck_payment_reversal_reason",
        "reversed_at IS NULL OR reversal_reason IS NOT NULL",
    ),
    (
        "documents",
        "ck_document_location",
        "managed_relative_path IS NOT NULL OR external_path IS NOT NULL",
    ),
)


def upgrade() -> None:
    for table, name, condition in CONSTRAINTS:
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_check_constraint(name, condition)


def downgrade() -> None:
    for table, name, _condition in CONSTRAINTS:
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_constraint(name, type_="check")
