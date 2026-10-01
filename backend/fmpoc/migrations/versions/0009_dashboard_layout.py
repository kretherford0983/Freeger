"""v1.5.0 CR-031: per-user dashboard section order and visibility.

Additive only - one nullable column (NULL = the default layout).

Revision ID: 0009_dashboard_layout
Revises: 0008_mfa
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_dashboard_layout"
down_revision = "0008_mfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("dashboard_layout", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("app_user") as b:
        b.drop_column("dashboard_layout")
