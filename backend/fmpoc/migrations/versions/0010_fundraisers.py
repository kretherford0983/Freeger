"""v1.6.0 CR-033: optional Fundraiser module.

Additive only - one column on workspace (module switch, off by default) and two new tables.

Revision ID: 0010_fundraisers
Revises: 0009_dashboard_layout
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_fundraisers"
down_revision = "0009_dashboard_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace", sa.Column("fundraisers_enabled", sa.Boolean(), nullable=False,
                                         server_default=sa.false()))
    op.create_table(
        "fundraiser",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", name="fk_fundraiser_workspace_id_workspace"),
                  nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("filter_text", sa.String(200), nullable=True),
        sa.Column("filter_regex", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("archived_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_fundraiser_workspace_id", "fundraiser", ["workspace_id"])
    op.create_index("ix_fundraiser_start_date", "fundraiser", ["start_date"])
    op.create_table(
        "fundraiser_budget",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fundraiser_id", sa.Integer(),
                  sa.ForeignKey("fundraiser.id", name="fk_fundraiser_budget_fundraiser_id_fundraiser"), nullable=False),
        sa.Column("fiscal_year_id", sa.Integer(),
                  sa.ForeignKey("fiscal_year.id", name="fk_fundraiser_budget_fiscal_year_id_fiscal_year"), nullable=False),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budget.id", name="fk_fundraiser_budget_budget_id_budget"),
                  nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),  # INCOME | EXPENSE
        sa.UniqueConstraint("fundraiser_id", "fiscal_year_id", "kind", name="uq_fundraiser_budget_fy_kind"),
    )
    op.create_index("ix_fundraiser_budget_fundraiser_id", "fundraiser_budget", ["fundraiser_id"])
    op.create_index("ix_fundraiser_budget_budget_id", "fundraiser_budget", ["budget_id"])


def downgrade() -> None:
    op.drop_table("fundraiser_budget")
    op.drop_table("fundraiser")
    with op.batch_alter_table("workspace") as b:
        b.drop_column("fundraisers_enabled")
