"""v1.2.1: per-allocation "no attachment will be provided" marker (CR-005 revision).

Additive only - new columns on transaction_allocation; existing rows default to no_attachment = false.

Revision ID: 0004_allocation_no_attachment
Revises: 0003_transfers_no_attachment
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_allocation_no_attachment"
down_revision = "0003_transfers_no_attachment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transaction_allocation", sa.Column("no_attachment", sa.Boolean(), nullable=False,
                                                      server_default=sa.false()))
    op.add_column("transaction_allocation", sa.Column("no_attachment_reason", sa.String(length=500), nullable=True))
    op.add_column("transaction_allocation", sa.Column("no_attachment_set_at", sa.DateTime(), nullable=True))
    op.add_column("transaction_allocation", sa.Column("no_attachment_set_by_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transaction_allocation") as b:
        for c in ("no_attachment_set_by_user_id", "no_attachment_set_at", "no_attachment_reason", "no_attachment"):
            b.drop_column(c)
