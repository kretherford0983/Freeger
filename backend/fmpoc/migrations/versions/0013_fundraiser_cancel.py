"""v1.6.4 CR-037: a fundraiser can be marked as cancelled (did not take place as planned).

Additive only - three nullable columns.

Revision ID: 0013_fundraiser_cancel
Revises: 0012_reminders
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_fundraiser_cancel"
down_revision = "0012_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fundraiser", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("fundraiser", sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True))
    op.add_column("fundraiser", sa.Column("cancel_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("fundraiser") as b:
        b.drop_column("cancel_reason")
        b.drop_column("cancelled_by_user_id")
        b.drop_column("cancelled_at")
