"""v1.4.1 CR-020: per-user choice of dashboard charts.

Additive only - one nullable column (NULL = the default set of charts).

Revision ID: 0007_dashboard_charts
Revises: 0006_signature_templates
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_dashboard_charts"
down_revision = "0006_signature_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("dashboard_charts", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("app_user") as b:
        b.drop_column("dashboard_charts")
