"""Drop the receipt of the one-time v3 reconciliation.

The reconciliation ran once and its code is gone, so nothing reads the receipt.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE reconciliation_receipt")


def downgrade() -> None:
    # Recreates the table empty; the dropped receipt is only in backups.
    op.execute("""
        CREATE TABLE reconciliation_receipt (
            id text PRIMARY KEY CHECK (id = 'v3-final'),
            input_hash text NOT NULL,
            plan_hash text NOT NULL,
            result jsonb NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
    """)
