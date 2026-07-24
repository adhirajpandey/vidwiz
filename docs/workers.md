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
  - CLI args: `--timeout` and optional `--api-url`
  - Internal API base URL resolution: `--api-url` -> `INTERNAL_API_URL`; exits on startup if neither is set
- **Metadata helper**: `backend/workers/scripts/metadata-helper.py`
  - Polls `/v2/internal/tasks?type=metadata` with long-poll timeout (default 30s)
  - Fetches metadata via `yt_dlp`
  - Submits results to `/v2/internal/tasks/{id}/result`
  - CLI args: `--timeout` and optional `--api-url`
  - Internal API base URL resolution: `--api-url` -> `INTERNAL_API_URL`; exits on startup if neither is set

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

### Lambda Infrastructure and Delivery
- `infra/` defines all three production functions, queues, the transcript
  bucket, event sources, log groups, and separate execution roles in
  `vidwiz-stack`.
- Canonical function names are `vidwiz-prod-transcript-dispatcher`,
  `vidwiz-prod-ai-note-worker`, and `vidwiz-prod-ai-summary-worker`.
- `.github/workflows/aws-infrastructure.yml` validates pull requests without
  AWS credentials or production secrets. Its production job is deliberately
  `workflow_dispatch`-only until the initial manual deployment and cutover
  succeed.
- The deployment job assumes `VidwizGitHubDeployRole` through GitHub OIDC,
  rejects an unexpected AWS account, and uses only the production CDK
  deployment, file-publishing, and lookup bootstrap roles.
- Each package contains one source renamed to root-level
  `lambda_function.py` plus its hash-pinned Python 3.13 dependencies. Builds
  use the pinned official Lambda Python image and produce deterministic ZIPs.
- Packaging validates integrity, limits, exclusions, dependencies, and a
  smoke import of `lambda_function.lambda_handler`.
- Regenerate the committed lock files from their `.in` files with Python 3.13 and `pip-compile --generate-hashes` when dependencies change.
- Production memory and timeout values must be captured from the legacy
  functions and supplied in `LAMBDA_ENV_FILE`; synthesis rejects missing
  values rather than selecting migration defaults.
- See `docs/aws-infrastructure.md` for validation, initial rollout, access,
  recovery, and cleanup boundaries.

## Data & Storage
- **Transcripts**: Stored in S3 at `transcripts/{video_id}.json` when configured.
- **Tasks**: Stored in the DB (`tasks` table) and polled via `/v2/internal/tasks`.
- **Queues**: SQS for AI note generation and AI summaries.

## Configuration (Common)
- Internal API access: `VIDWIZ_ENDPOINT`, `VIDWIZ_TOKEN` (admin token)
- Helpers: `ADMIN_TOKEN`, `INTERNAL_API_URL` or `--api-url` (base), `--timeout`
- S3 access: `S3_BUCKET_NAME`, AWS credentials
- LLM provider: OpenRouter (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`)
