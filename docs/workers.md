# VidWiz Workers

## Purpose
Describe background helpers and Lambdas used for transcript/metadata fetching and AI generation.

## Components
### Helpers (Long-Running)
- **Transcript helper**: `backend/workers/scripts/transcript-helper.py`
  - Polls `/v2/internal/tasks?type=transcript` with long-poll timeout (default 30s)
  - Fetches transcripts via `youtube_transcript_api` (languages: `en`, `hi`)
  - Normalizes transcript items by renaming `start` -> `offset`
  - Submits results to `/v2/internal/tasks/{id}/result`
  - CLI args: `--timeout` and `--api-url` (default `https://api.vidwiz.online`)
- **Metadata helper**: `backend/workers/scripts/metadata-helper.py`
  - Polls `/v2/internal/tasks?type=metadata` with long-poll timeout (default 30s)
  - Fetches metadata via `yt_dlp`
  - Submits results to `/v2/internal/tasks/{id}/result`
  - CLI args: `--timeout` and `--api-url` (default `https://api.vidwiz.online`)

### Lambdas
- **AI Note Lambda**: `backend/workers/lambdas/ai-note.py`
  - Triggered by SQS messages containing note payloads (minimal: `{ id, video_id, timestamp, user_id }`)
  - Fetches transcript from S3 with retry/backoff
  - Extracts context around the timestamp (buffer + surrounding segments)
  - Generates a one-line note with length constraints and retries on length mismatch
  - Uses OpenRouter via OpenAI-compatible API (`OPENROUTER_API_KEY`)
  - Updates note via `/v2/internal/notes/{id}` (sets `generated_by_ai=true`)
  - Falls back to `/v2/internal/videos/{video_id}` to resolve title when not provided in payload
  - Configurable: `TRANSCRIPT_BUFFER_SECONDS`, `CONTEXT_SEGMENTS`, `MIN_NOTE_LENGTH`, `MAX_NOTE_LENGTH`, `MAX_RETRIES`

- **AI Summary Lambda**: `backend/workers/lambdas/ai-summary.py`
  - Triggered by SQS messages containing `{ video_id }`
  - Reads transcript from S3 with retry/backoff and builds a full transcript string
  - Skips generation if summary already exists
  - Uses OpenRouter via OpenAI-compatible API (`OPENROUTER_API_KEY`)
  - Updates video via `/v2/internal/videos/{id}/summary`
  - Configurable: `MIN_SUMMARY_LENGTH`, `MAX_SUMMARY_LENGTH`, `MAX_RETRIES`

- **Task Dispatcher Lambda**: `backend/workers/lambdas/tasks-dispatcher.py`
  - Triggered by S3 transcript uploads (or manual `video_ids` input)
  - On S3 event: enqueues summary jobs to summary SQS
  - For all video IDs: fetches eligible AI-note tasks via `/v2/internal/videos/{video_id}/ai-notes` and batches them to the AI note SQS (batch size 10)
  - Notes fetch uses admin token (`VIDWIZ_TOKEN`)

## Data & Storage
- **Transcripts**: Stored in S3 at `transcripts/{video_id}.json` when configured.
- **Tasks**: Stored in the DB (`tasks` table) and polled via `/v2/internal/tasks`.
- **Queues**: SQS for AI note generation and AI summaries.

## Configuration (Common)
- Internal API access: `VIDWIZ_ENDPOINT`, `VIDWIZ_TOKEN` (admin token)
- Helpers: `ADMIN_TOKEN`, `--api-url` (base), `--timeout`
- S3 access: `S3_BUCKET_NAME`, AWS credentials
- LLM provider: OpenRouter (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`)
