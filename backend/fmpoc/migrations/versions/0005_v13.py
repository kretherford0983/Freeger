"""v1.3.0: Fiscal Year document types, request keys (duplicate protection), missing-check acknowledgements.

Additive only - new tables and new nullable/defaulted columns; existing values are not changed except that
existing Fiscal Year attachments are labelled UNSPECIFIED (their previous meaning).

Revision ID: 0005_v13
Revises: 0004_allocation_no_attachment
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_v13"
down_revision = "0004_allocation_no_attachment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CR-007 / CR-008: Fiscal Year document types; system-generated Close report
    op.add_column("attachment", sa.Column("document_type", sa.String(length=20), nullable=True))
    op.add_column("attachment", sa.Column("system_generated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE attachment SET document_type = 'UNSPECIFIED' WHERE fiscal_year_id IS NOT NULL")
    op.add_column("fiscal_year", sa.Column("approval_no_attachment", sa.Boolean(), nullable=False,
                                           server_default=sa.false()))
    op.add_column("fiscal_year", sa.Column("approval_no_attachment_reason", sa.String(length=500), nullable=True))
    op.add_column("fiscal_year", sa.Column("approval_no_attachment_set_at", sa.DateTime(), nullable=True))
    op.add_column("fiscal_year", sa.Column("approval_no_attachment_set_by_user_id", sa.Integer(), nullable=True))
    # CR-014: collapsed left navigation, remembered per user like the theme
    op.add_column("app_user", sa.Column("nav_collapsed", sa.Boolean(), nullable=False, server_default=sa.false()))
    # CR-011: one-time request keys make a repeated submit (double click, retry) return the original record
    op.create_table(
        "request_key",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False, index=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("result_ids", sa.String(length=100), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", name="uq_request_key_ws_key"),
    )
    # CR-012: "confirmed not missing" check numbers / ranges
    op.create_table(
        "check_number_acknowledgement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False, index=True),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_account.id"), nullable=False, index=True),
        sa.Column("first_number", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("check_number_acknowledgement")
    op.drop_table("request_key")
    with op.batch_alter_table("app_user") as b:
        b.drop_column("nav_collapsed")
    with op.batch_alter_table("fiscal_year") as b:
        for c in ("approval_no_attachment_set_by_user_id", "approval_no_attachment_set_at",
                  "approval_no_attachment_reason", "approval_no_attachment"):
            b.drop_column(c)
    with op.batch_alter_table("attachment") as b:
        b.drop_column("system_generated")
        b.drop_column("document_type")
