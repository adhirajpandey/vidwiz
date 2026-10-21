"""Fill video titles from their metadata.

v2 kept the title only in video_metadata for videos opened through Ask, so
imported videos without a saved note have no title. v3 copies the metadata
title when metadata arrives; this does the same for the imported rows.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE videos
        SET title = video_metadata->>'title'
        WHERE title IS NULL
          AND nullif(trim(video_metadata->>'title'), '') IS NOT NULL;
        """
    )


def downgrade() -> None:
    # The copied titles match the metadata, so they stay.
    pass
