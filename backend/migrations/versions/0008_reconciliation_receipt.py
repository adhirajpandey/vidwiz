"""Receipt for the one-time final v3 reconciliation.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE reconciliation_receipt (
            id text PRIMARY KEY CHECK (id = 'v3-final'),
            input_hash text NOT NULL,
            plan_hash text NOT NULL,
            result jsonb NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    # Never erase the evidence needed to prevent a duplicate import.
    raise NotImplementedError(
        "Retain the reconciliation receipt; restore a backup instead"
    )
