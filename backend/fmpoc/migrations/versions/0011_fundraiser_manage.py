"""v1.6.1 CR-034: fundraiser buckets, special classifications, exclusions and fundraiser documents.

Additive only - four new tables and one nullable column on attachment.

Revision ID: 0011_fundraiser_manage
Revises: 0010_fundraisers
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_fundraiser_manage"
down_revision = "0010_fundraisers"
branch_labels = None
depends_on = None


def _fk(table, col, target):
    return sa.ForeignKey(f"{target}.id", name=f"fk_{table}_{col}_{target}")


def upgrade() -> None:
    op.create_table(
        "fundraiser_bucket",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fundraiser_id", sa.Integer(), _fk("fundraiser_bucket", "fundraiser_id", "fundraiser"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_fundraiser_bucket_fundraiser_id", "fundraiser_bucket", ["fundraiser_id"])
    op.create_table(
        "fundraiser_exclusion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fundraiser_id", sa.Integer(), _fk("fundraiser_exclusion", "fundraiser_id", "fundraiser"), nullable=False),
        sa.Column("allocation_id", sa.Integer(), _fk("fundraiser_exclusion", "allocation_id", "transaction_allocation"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("fundraiser_id", "allocation_id", name="uq_fundraiser_exclusion_line"),
    )
    op.create_index("ix_fundraiser_exclusion_fundraiser_id", "fundraiser_exclusion", ["fundraiser_id"])
    op.create_table(
        "fundraiser_classification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fundraiser_id", sa.Integer(), _fk("fundraiser_classification", "fundraiser_id", "fundraiser"), nullable=False),
        sa.Column("allocation_id", sa.Integer(), _fk("fundraiser_classification", "allocation_id", "transaction_allocation"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),  # CASH_FLOAT_OUT | CASH_FLOAT_RETURNED
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("fundraiser_id", "allocation_id", name="uq_fundraiser_classification_line"),
    )
    op.create_index("ix_fundraiser_classification_fundraiser_id", "fundraiser_classification", ["fundraiser_id"])
    op.create_table(
        "fundraiser_bucket_line",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket_id", sa.Integer(), _fk("fundraiser_bucket_line", "bucket_id", "fundraiser_bucket"), nullable=False),
        sa.Column("allocation_id", sa.Integer(), _fk("fundraiser_bucket_line", "allocation_id", "transaction_allocation"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("bucket_id", "allocation_id", name="uq_fundraiser_bucket_line"),
    )
    op.create_index("ix_fundraiser_bucket_line_bucket_id", "fundraiser_bucket_line", ["bucket_id"])
    op.add_column("attachment", sa.Column("fundraiser_id", sa.Integer(), nullable=True))
    op.create_index("ix_attachment_fundraiser_id", "attachment", ["fundraiser_id"])


def downgrade() -> None:
    op.drop_index("ix_attachment_fundraiser_id", "attachment")
    with op.batch_alter_table("attachment") as b:
        b.drop_column("fundraiser_id")
    op.drop_table("fundraiser_bucket_line")
    op.drop_table("fundraiser_classification")
    op.drop_table("fundraiser_exclusion")
    op.drop_table("fundraiser_bucket")
