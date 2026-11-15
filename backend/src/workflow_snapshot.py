"""Read current items without changing or deleting historical task attempts.

Legacy failures without an explicit kind are classified only from narrow,
unambiguous messages. Unknown causes remain failures for investigation.
"""

from sqlalchemy import text

# Task status is a PostgreSQL enum storing uppercase names; product states are
# text. Latest means most recently created attempt (id breaks timestamp ties).
CURRENT_ITEMS = """
WITH ranked AS (
    SELECT t.*, row_number() OVER (
        PARTITION BY task_type,
          coalesce(task_details->>'video_id', task_details->>'moment_id', id::text)
        ORDER BY created_at DESC, id DESC
    ) AS rank
    FROM tasks t
    WHERE task_type IN ('fetch_metadata', 'fetch_transcript', 'resolve_title')
), latest AS (
    SELECT *, CASE
      WHEN worker_details->>'error_kind' IN ('unavailable', 'no_transcript')
        THEN 'unavailable'
      WHEN coalesce(worker_details->>'error_kind', 'worker_error')
           NOT IN ('worker_error', 'not_found') THEN 'failed'
      WHEN coalesce(worker_details->>'error_message', '') ~*
        '(sign in to confirm|ipblocked|requestblocked|proxyerror|timed out)'
        THEN 'failed'
      WHEN coalesce(worker_details->>'error_message', '') ~*
        '(private video|video has been removed|video has been deleted|video unavailable|video is no longer available|subtitles are disabled|transcriptsdisabled|no transcripts were found|notranscriptfound)'
        THEN 'unavailable'
      ELSE 'failed' END AS failure_state
    FROM ranked WHERE rank = 1
), durations AS (
    SELECT video_id, CASE
      WHEN video_metadata->>'duration' ~ '^[0-9]+([.][0-9]+)?$'
        THEN (video_metadata->>'duration')::numeric
      END AS duration
    FROM videos
), items AS (
    SELECT 'metadata' AS workflow,
      CASE
        WHEN t.status = 'PENDING' THEN 'pending'
        WHEN t.status = 'IN_PROGRESS' THEN 'in_progress'
        WHEN t.status = 'FAILED' AND
             (v.video_metadata IS NULL OR v.video_metadata::jsonb IN ('null', '{}'))
          THEN t.failure_state
      END AS state,
      coalesce(t.started_at, t.created_at) AS since
    FROM latest t JOIN videos v ON v.video_id = t.task_details->>'video_id'
    WHERE t.task_type = 'fetch_metadata'
    UNION ALL
    SELECT 'transcript',
      CASE
        WHEN v.transcript_status = 'ready' THEN NULL
        WHEN v.transcript_status = 'pending' THEN 'pending'
        WHEN t.status = 'COMPLETED' THEN 'unavailable'
        WHEN t.status = 'FAILED' THEN t.failure_state
        ELSE 'unknown'
      END,
      coalesce(t.completed_at, v.updated_at)
    FROM videos v LEFT JOIN latest t
      ON t.task_type = 'fetch_transcript' AND t.task_details->>'video_id' = v.video_id
    UNION ALL
    SELECT 'title_resolution',
      CASE
        WHEN m.resolve_status = 'resolving' THEN 'resolving'
        WHEN m.resolve_status = 'unresolved' THEN
          CASE WHEN jsonb_typeof(m.resolve_candidates) = 'array'
                     AND m.resolve_candidates <> '[]'::jsonb THEN 'awaiting_user'
               WHEN t.worker_details->>'error_kind' = 'not_found' THEN 'not_found'
               ELSE 'failed' END
      END, m.created_at
    FROM moments m LEFT JOIN latest t
      ON t.task_type = 'resolve_title' AND t.task_details->>'moment_id' = m.id::text
    UNION ALL
    SELECT 'ai_moment',
      CASE
        WHEN m.ai_status = 'invalid_timestamp' OR
             (m.ai_status IN ('waiting_transcript', 'queued', 'failed', 'no_transcript')
              AND d.duration > 0 AND m.at_seconds > d.duration) THEN 'invalid_timestamp'
        WHEN m.video_id IS NULL AND m.ai_status <> 'not_requested' THEN 'waiting_title'
        WHEN m.ai_status = 'no_transcript' THEN 'blocked'
        WHEN m.ai_status IN ('waiting_transcript', 'queued', 'failed') THEN m.ai_status
      END, m.created_at
    FROM moments m LEFT JOIN durations d USING (video_id)
    UNION ALL
    SELECT 'overview',
      CASE WHEN overview_status = 'no_transcript' THEN 'blocked'
           WHEN overview_status IN ('pending', 'queued', 'failed') THEN overview_status
      END, overview_status_at
    FROM videos
)
"""


def current_workflow_rows(db):
    return db.execute(
        text(
            CURRENT_ITEMS
            + """
        SELECT workflow, state, count(*), min(since)
        FROM items WHERE state IS NOT NULL GROUP BY workflow, state
    """
        )
    ).all()
