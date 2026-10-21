"""Full-text search over moments and transcript chunks.

Transcripts are split into passages stored in PostgreSQL so they can be
searched. Moments and passages get generated tsvector columns with GIN indexes,
and pg_trgm trigram indexes give a typo-tolerant fallback.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        CREATE TABLE transcript_chunks (
            id serial PRIMARY KEY,
            video_id text NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
            idx integer NOT NULL,
            start_seconds integer NOT NULL,
            end_seconds integer NOT NULL,
            text text NOT NULL,
            search tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            CONSTRAINT transcript_chunks_video_idx_key UNIQUE (video_id, idx),
            CONSTRAINT transcript_chunks_range_check
                CHECK (start_seconds >= 0 AND end_seconds >= start_seconds)
        );
        CREATE INDEX transcript_chunks_search_idx
            ON transcript_chunks USING gin (search);
        CREATE INDEX transcript_chunks_text_trgm_idx
            ON transcript_chunks USING gin (text gin_trgm_ops);

        -- The user's own words rank above the quoted transcript.
        ALTER TABLE moments ADD COLUMN search tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(note, '')), 'A')
            || setweight(to_tsvector('english', coalesce(ai_text, '')), 'A')
            || setweight(to_tsvector('english', coalesce(quote, '')), 'B')
        ) STORED;
        CREATE INDEX moments_search_idx ON moments USING gin (search);
        CREATE INDEX moments_text_trgm_idx ON moments USING gin (
            (coalesce(note, '') || ' ' || coalesce(ai_text, '')) gin_trgm_ops
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX moments_text_trgm_idx;
        DROP INDEX moments_search_idx;
        ALTER TABLE moments DROP COLUMN search;
        DROP TABLE transcript_chunks;
        """
    )
