"""Allow invalid capture timestamps to be shown without retrying AI.

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

STATES = "'not_requested', 'waiting_transcript', 'queued', 'ready', 'failed', 'no_transcript', 'insufficient_credits'"


def upgrade() -> None:
    op.execute("ALTER TABLE moments DROP CONSTRAINT moments_ai_status_check")
    op.execute(
        f"ALTER TABLE moments ADD CONSTRAINT moments_ai_status_check "
        f"CHECK (ai_status IN ({STATES}, 'invalid_timestamp'))"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE moments SET ai_status = 'failed' WHERE ai_status = 'invalid_timestamp'"
    )
    op.execute("ALTER TABLE moments DROP CONSTRAINT moments_ai_status_check")
    op.execute(
        f"ALTER TABLE moments ADD CONSTRAINT moments_ai_status_check CHECK (ai_status IN ({STATES}))"
    )
