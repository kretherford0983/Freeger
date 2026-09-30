"""v1.4.1 CR-018: multi-factor authentication (TOTP, recovery codes, trusted browsers).

Additive only - three new tables and one nullable column on auth_session (existing sessions stay signed in; MFA
applies from the next sign-in).

Revision ID: 0008_mfa
Revises: 0007_dashboard_charts
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_mfa"
down_revision = "0007_dashboard_charts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_session", sa.Column("mfa_pending", sa.String(length=10), nullable=True))
    op.create_table(
        "user_mfa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False, unique=True),
        sa.Column("secret_enc", sa.String(length=200), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("last_step", sa.Integer(), nullable=True),
        sa.Column("pending_secret_enc", sa.String(length=200), nullable=True),
        sa.Column("pending_created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "mfa_recovery_code",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False, index=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "trusted_device",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("trusted_device")
    op.drop_table("mfa_recovery_code")
    op.drop_table("user_mfa")
    with op.batch_alter_table("auth_session") as b:
        b.drop_column("mfa_pending")
