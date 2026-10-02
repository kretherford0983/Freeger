"""v1.6.3 CR-036: reminders and notifications.

Additive only - one new table.

Revision ID: 0012_reminders
Revises: 0011_fundraiser_manage
"""
import sqlalchemy as sa
from alembic import op

revision = "0012_reminders"
down_revision = "0011_fundraiser_manage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminder",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", name="fk_reminder_workspace_id_workspace"), nullable=False),
        sa.Column("scope", sa.String(12), nullable=False),  # PERSONAL | ORGANIZATION
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("app_user.id", name="fk_reminder_owner_user_id_app_user"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("notify_days_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("link_type", sa.String(16), nullable=True),  # FISCAL_YEAR | BUDGET | BANK_ACCOUNT
        sa.Column("link_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_reminder_workspace_id", "reminder", ["workspace_id"])
    op.create_index("ix_reminder_due_date", "reminder", ["due_date"])
    op.create_index("ix_reminder_owner_user_id", "reminder", ["owner_user_id"])


def downgrade() -> None:
    op.drop_table("reminder")
