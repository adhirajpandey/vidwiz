"""Embeddings for meaning-based search, and keyword search over video cards.

Transcript passages, moments and video cards get a nullable 1024-number
embedding; null means not embedded yet. There is no vector index, so scans are
exact. A video card is its title, channel, summary and key points; a generated
tsvector with a GIN index makes it keyword-searchable.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS vector;

        ALTER TABLE transcript_chunks ADD COLUMN embedding vector(1024);
        ALTER TABLE moments ADD COLUMN embedding vector(1024);
        ALTER TABLE videos ADD COLUMN card_embedding vector(1024);

        -- The title and channel weigh more than the summary and key points.
        ALTER TABLE videos ADD COLUMN card_search tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A')
            || setweight(
                to_tsvector('english', coalesce(video_metadata ->> 'uploader', '')),
                'A'
            )
            || setweight(to_tsvector('english', coalesce(summary, '')), 'B')
            || setweight(
                to_tsvector(
                    'english',
                    coalesce(
                        jsonb_path_query_array(
                            miscellaneous_data::jsonb, '$.key_points[*].text'
                        )::text,
                        ''
                    )
                ),
                'B'
            )
        ) STORED;
        CREATE INDEX videos_card_search_idx ON videos USING gin (card_search);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX videos_card_search_idx;
        ALTER TABLE videos DROP COLUMN card_search;
        ALTER TABLE videos DROP COLUMN card_embedding;
        ALTER TABLE moments DROP COLUMN embedding;
        ALTER TABLE transcript_chunks DROP COLUMN embedding;
        """
    )
