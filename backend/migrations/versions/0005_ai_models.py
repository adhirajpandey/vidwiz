"""Record which model wrote each AI moment line.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE moments ADD COLUMN ai_model text")


def downgrade() -> None:
    op.execute("ALTER TABLE moments DROP COLUMN ai_model")
