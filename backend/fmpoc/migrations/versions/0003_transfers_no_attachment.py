"""v1.2: transfer legs and "no attachment will be provided" flag on register transactions.

Additive only (new nullable / defaulted columns + index) - existing rows are preserved unchanged:
no_attachment defaults to false and transfer_group to NULL.

Revision ID: 0003_transfers_no_attachment
Revises: 0002_audit_append_only
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_transfers_no_attachment"
down_revision = "0002_audit_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("register_transaction", sa.Column("transfer_group", sa.String(length=36), nullable=True))
    op.add_column("register_transaction", sa.Column("no_attachment", sa.Boolean(), nullable=False,
                                                    server_default=sa.false()))
    op.add_column("register_transaction", sa.Column("no_attachment_reason", sa.String(length=500), nullable=True))
    op.add_column("register_transaction", sa.Column("no_attachment_set_at", sa.DateTime(), nullable=True))
    op.add_column("register_transaction", sa.Column("no_attachment_set_by_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_register_transaction_transfer_group"), "register_transaction", ["transfer_group"])


def downgrade() -> None:
    with op.batch_alter_table("register_transaction") as b:
        b.drop_index("ix_register_transaction_transfer_group")
        for c in ("no_attachment_set_by_user_id", "no_attachment_set_at", "no_attachment_reason", "no_attachment",
                  "transfer_group"):
            b.drop_column(c)
