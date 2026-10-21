"""Explicit transcript and overview states for videos.

transcript_available becomes transcript_status (pending, ready, unavailable).
Videos without a transcript and without an active transcript task become
unavailable.
Videos gain overview_status (pending, queued, ready, failed, no_transcript) and
the time it last changed. Existing summaries count as ready, including older
ones without key points; the overview backfill regenerates those.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-19
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TRANSCRIPT_STATUSES = ("pending", "ready", "unavailable")
OVERVIEW_STATUSES = ("pending", "queued", "ready", "failed", "no_transcript")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE videos
            ADD COLUMN transcript_status text,
            ADD COLUMN overview_status text,
            ADD COLUMN overview_status_at timestamp without time zone
                NOT NULL DEFAULT now();

        -- A transcript is pending only while a transcript task is still active
        -- or will be retried; otherwise nothing is fetching it, so it is
        -- unavailable until a new capture schedules another attempt.
        UPDATE videos v SET transcript_status = CASE
            WHEN v.transcript_available THEN 'ready'
            WHEN EXISTS (
                SELECT 1
                FROM tasks t
                WHERE t.task_type = 'fetch_transcript'
                  AND t.task_details->>'video_id' = v.video_id
                  AND (
                      t.status IN ('PENDING', 'IN_PROGRESS')
                      OR (t.status = 'FAILED' AND coalesce(t.retry_count, 0) < 3)
                  )
            ) THEN 'pending'
            ELSE 'unavailable'
        END;

        UPDATE videos SET overview_status = CASE
            WHEN summary IS NOT NULL THEN 'ready'
            WHEN transcript_status = 'unavailable' THEN 'no_transcript'
            ELSE 'pending'
        END;

        ALTER TABLE videos
            ALTER COLUMN transcript_status SET NOT NULL,
            ALTER COLUMN transcript_status SET DEFAULT 'pending',
            ALTER COLUMN overview_status SET NOT NULL,
            ALTER COLUMN overview_status SET DEFAULT 'pending',
            ADD CONSTRAINT videos_transcript_status_check
                CHECK (transcript_status IN ({_in(TRANSCRIPT_STATUSES)})),
            ADD CONSTRAINT videos_overview_status_check
                CHECK (overview_status IN ({_in(OVERVIEW_STATUSES)})),
            DROP COLUMN transcript_available;

        CREATE INDEX videos_overview_queued_idx ON videos (overview_status_at)
            WHERE overview_status = 'queued';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX videos_overview_queued_idx;
        ALTER TABLE videos ADD COLUMN transcript_available boolean DEFAULT false;
        UPDATE videos SET transcript_available = transcript_status = 'ready';
        ALTER TABLE videos
            DROP COLUMN transcript_status,
            DROP COLUMN overview_status,
            DROP COLUMN overview_status_at;
        """
    )
