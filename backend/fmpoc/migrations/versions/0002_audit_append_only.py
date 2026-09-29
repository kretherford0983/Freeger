"""Append-only audit trail enforced at the database level (BR-075, AC-AUD-004).

Revision ID: 0002_audit_append_only
Revises: 0001_initial
"""
from alembic import op

revision = "0002_audit_append_only"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TRIGGER audit_event_no_update BEFORE UPDATE ON audit_event
        BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
    """)
    op.execute("""
        CREATE TRIGGER audit_event_no_delete BEFORE DELETE ON audit_event
        BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_event_no_update")
    op.execute("DROP TRIGGER IF EXISTS audit_event_no_delete")
