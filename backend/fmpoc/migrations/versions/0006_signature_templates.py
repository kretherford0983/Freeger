"""v1.4.1 CR-016: saved wording for the audit review signature page.

Additive only - one new table.

Revision ID: 0006_signature_templates
Revises: 0005_v13
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_signature_templates"
down_revision = "0005_v13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signature_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("signature_template")
