"""Candidate videos for title captures that could not be resolved confidently.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE moments ADD COLUMN resolve_candidates jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE moments DROP COLUMN resolve_candidates")
