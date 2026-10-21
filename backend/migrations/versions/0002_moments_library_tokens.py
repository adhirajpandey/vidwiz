"""Moments, library items, API tokens, and conversation scopes.

Notes become moments with numeric times and separate fields for the AI line
and the user's note. AI and video resolution states are explicit. Saved videos
get their own table, long-term tokens are hashed into api_tokens, and
conversations gain a video or library scope.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

AI_STATUSES = (
    "not_requested",
    "waiting_transcript",
    "queued",
    "ready",
    "failed",
    "no_transcript",
    "insufficient_credits",
)
RESOLVE_STATUSES = ("resolving", "resolved", "unresolved")
SOURCES = ("phone", "extension", "web", "api", "legacy")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE notes RENAME TO moments;
        ALTER SEQUENCE notes_id_seq RENAME TO moments_id_seq;
        ALTER INDEX notes_pkey RENAME TO moments_pkey;
        ALTER TABLE moments RENAME CONSTRAINT notes_user_id_fkey TO moments_user_id_fkey;
        ALTER TABLE moments RENAME CONSTRAINT notes_video_id_fkey TO moments_video_id_fkey;

        ALTER TABLE moments
            ADD COLUMN at_seconds integer,
            ADD COLUMN quote text,
            ADD COLUMN quote_start_seconds integer,
            ADD COLUMN ai_text text,
            ADD COLUMN note text,
            ADD COLUMN ai_status text,
            ADD COLUMN resolve_status text,
            ADD COLUMN source text,
            ADD COLUMN pending_title text,
            ADD COLUMN pending_channel text;

        -- "h:mm:ss" or "m:ss" to seconds. One legacy value is negative; it
        -- becomes zero.
        UPDATE moments SET at_seconds = CASE
            WHEN "timestamp" LIKE '-%' THEN 0
            ELSE (
                SELECT sum(part::int * power(60, array_length(parts, 1) - position))::int
                FROM (SELECT string_to_array("timestamp", ':') AS parts) AS split,
                     unnest(parts) WITH ORDINALITY AS piece(part, position)
            )
        END;

        UPDATE moments SET
            ai_text = CASE WHEN generated_by_ai THEN text END,
            note = CASE WHEN NOT generated_by_ai THEN text END,
            ai_status = CASE WHEN generated_by_ai THEN 'ready' ELSE 'not_requested' END,
            resolve_status = 'resolved',
            source = 'legacy';

        ALTER TABLE moments
            DROP COLUMN "timestamp",
            DROP COLUMN text,
            DROP COLUMN generated_by_ai,
            ALTER COLUMN video_id DROP NOT NULL,
            ALTER COLUMN at_seconds SET NOT NULL,
            ALTER COLUMN ai_status SET NOT NULL,
            ALTER COLUMN resolve_status SET NOT NULL,
            ALTER COLUMN source SET NOT NULL,
            ADD CONSTRAINT moments_at_seconds_check CHECK (at_seconds >= 0),
            ADD CONSTRAINT moments_ai_status_check CHECK (ai_status IN ({_in(AI_STATUSES)})),
            ADD CONSTRAINT moments_resolve_status_check
                CHECK (resolve_status IN ({_in(RESOLVE_STATUSES)})),
            ADD CONSTRAINT moments_source_check CHECK (source IN ({_in(SOURCES)})),
            ADD CONSTRAINT moments_video_resolved_check
                CHECK ((video_id IS NOT NULL) = (resolve_status = 'resolved'));

        CREATE INDEX moments_user_video_at_idx ON moments (user_id, video_id, at_seconds);

        -- AI charges now reference moments. Same IDs, so charge-once still holds.
        UPDATE credits_ledger SET ref_type = 'moment', reason = 'ai_moment'
        WHERE ref_type = 'note' AND reason = 'ai_note';

        CREATE TABLE library_items (
            user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            video_id text NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
            added_at timestamp with time zone NOT NULL DEFAULT now(),
            last_opened_at timestamp with time zone,
            PRIMARY KEY (user_id, video_id)
        );

        INSERT INTO library_items (user_id, video_id, added_at)
        SELECT user_id, video_id, min(created_at) FROM (
            SELECT user_id, video_id, created_at FROM moments
            UNION ALL
            SELECT c.user_id, c.video_id, c.created_at
            FROM conversations c
            JOIN videos v ON v.video_id = c.video_id
            WHERE c.user_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM messages m
                  WHERE m.conversation_id = c.id AND m.role = 'user'
              )
        ) AS saved
        GROUP BY user_id, video_id;

        CREATE TABLE api_tokens (
            id serial PRIMARY KEY,
            user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name text NOT NULL,
            token_hash text NOT NULL UNIQUE,
            token_hint text NOT NULL,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            last_used_at timestamp with time zone,
            revoked_at timestamp with time zone
        );

        -- Existing long-term tokens keep working: they are looked up by hash.
        INSERT INTO api_tokens (user_id, name, token_hash, token_hint)
        SELECT id, 'Legacy token',
               encode(sha256(convert_to(long_term_token, 'UTF8')), 'hex'),
               right(long_term_token, 4)
        FROM users WHERE long_term_token IS NOT NULL;

        ALTER TABLE users DROP COLUMN long_term_token;

        UPDATE users SET profile_data = (
            (profile_data::jsonb - 'ai_notes_enabled')
            || jsonb_build_object(
                'ai_moments_default',
                coalesce((profile_data->>'ai_notes_enabled')::boolean, false)
            )
        )::json
        WHERE profile_data IS NOT NULL;

        ALTER TABLE conversations
            ADD COLUMN scope text NOT NULL DEFAULT 'video',
            ALTER COLUMN video_id DROP NOT NULL,
            ADD CONSTRAINT conversations_scope_check CHECK (scope IN ('video', 'library')),
            ADD CONSTRAINT conversations_scope_video_check
                CHECK ((scope = 'video') = (video_id IS NOT NULL));
        """
    )


def downgrade() -> None:
    raise NotImplementedError(
        "0002 drops legacy columns and hashes tokens; restore from a dump instead."
    )
