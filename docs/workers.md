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
  - Internal API base URL resolution: `--api-url` -> `VIDWIZ_INTERNAL_API_BASE_URL`; exits on startup if neither is set
- **Metadata helper**: `backend/workers/scripts/metadata-helper.py`
  - Polls `/v2/internal/tasks?type=metadata` with long-poll timeout (default 30s)
  - Fetches metadata via `yt_dlp`
  - Submits results to `/v2/internal/tasks/{id}/result`
  - CLI args: `--timeout` and optional `--api-url`
  - Internal API base URL resolution: `--api-url` -> `VIDWIZ_INTERNAL_API_BASE_URL`; exits on startup if neither is set

The production helper processes are owned by the `metadata-helper` and
`transcript-helper` services in `docker-compose.yml`; no repository workflow
or systemd unit manages parallel helper processes.

### Lambdas
- **AI Note Lambda**: `backend/workers/lambdas/ai_note_worker`
  - `handler.py` parses SQS events and delegates to the functional
    `note_service.py` module.
  - Triggered by SQS messages containing note payloads (minimal: `{ id, video_id, timestamp, user_id }`)
  - Fetches transcript from S3 with retry/backoff
  - Extracts context around the timestamp (buffer + surrounding segments)
  - Generates a one-line note with length constraints and retries on length mismatch
  - Uses OpenRouter via OpenAI-compatible API (`OPENROUTER_API_KEY`)
  - Updates note via `/v2/internal/notes/{id}` (sets `generated_by_ai=true`)
  - Fails the invocation when transcript/context, generation, or persistence fails so SQS retries the record
  - Falls back to `/v2/internal/videos/{video_id}` to resolve title when not provided in payload
  - Configurable: `TRANSCRIPT_BUFFER_SECONDS`, `CONTEXT_SEGMENTS`, `MIN_NOTE_LENGTH`, `MAX_NOTE_LENGTH`, `MAX_RETRIES`

- **AI Summary Lambda**: `backend/workers/lambdas/ai_summary_worker`
  - `handler.py` parses SQS events and delegates to the functional
    `summary_service.py` module.
  - Triggered by SQS messages containing `{ video_id }`
  - Reads transcript from S3 with retry/backoff and builds a full transcript string
  - Skips generation if summary already exists
  - Uses one OpenRouter structured-output request to generate the summary and
    exactly three video-specific Wiz questions
  - Enforces summary and question character limits in the prompt and local
    validation. The JSON Schema enforces the response shape and exactly three
    questions while avoiding constraints unsupported by some providers
  - Updates the summary and `miscellaneous_data.suggested_questions` together
    via `/v2/internal/videos/{id}/summary`
  - Propagates processing exceptions so the single-record SQS batch is retried
  - Configurable: `MIN_SUMMARY_LENGTH`, `MAX_SUMMARY_LENGTH`,
    `MIN_QUESTION_LENGTH` (default 20), `MAX_QUESTION_LENGTH` (default 120),
    `MAX_RETRIES`

- **Task Dispatcher Lambda**:
  `backend/workers/lambdas/transcript_dispatcher`
  - `handler.py` parses S3/manual events and delegates to the functional
    `dispatch_service.py` module.
  - Triggered by S3 transcript uploads (or manual `video_ids` input)
  - On S3 event: enqueues summary jobs to summary SQS
  - For all video IDs: fetches eligible AI-note tasks via `/v2/internal/videos/{video_id}/ai-notes` and batches them to the AI note SQS (batch size 10)
  - Notes fetch uses `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`
  - Propagates unhandled dispatch failures so Lambda retry/DLQ handling can run

### Lambda Logging
Lambdas log processing milestones and failures with safe identifiers and
counts. They do not log complete events, request or response bodies, prompts,
transcripts, generated content, authorization values, or provider error
payloads.

### Lambda Infrastructure and Delivery
- `infra/` defines all three production functions, queues, the transcript
  bucket, event sources, log groups, and separate execution roles in
  `vidwiz-stack`.
- Canonical function names are `vidwiz-prod-transcript-dispatcher`,
  `vidwiz-prod-ai-note-worker`, and `vidwiz-prod-ai-summary-worker`.
- `.github/workflows/aws-infrastructure.yml` validates and deploys production
  infrastructure only when manually dispatched from `main`.
- The deployment job assumes `VidwizGitHubDeployRole` through GitHub OIDC,
  rejects an unexpected AWS account, and uses only the production CDK
  deployment, file-publishing, and lookup bootstrap roles.
- Each Lambda has its own source directory and explicit infrastructure
  specification. It contains a root-level handler, domain service module,
  `pyproject.toml`, committed `uv.lock`, and colocated tests. CDK excludes tests
  and Python bytecode caches, then bundles the remaining directory in a
  Lambda-compatible Docker container during synthesis. The AI-note and
  AI-summary services use common
  configuration, clients, models, and transcript utilities from
  `backend/workers/shared/vidwiz_worker`. CDK mounts and copies that package
  into each AI worker's staging directory, so both retain independently
  deployable ZIPs without duplicating common implementation.
- Worker tests are colocated with their owning Lambda or shared module and are
  discovered by the backend pytest configuration.
- CDK stages each generated ZIP asset in `cdk.out` and publishes it during
  deployment. Dependency changes are made in the worker's `pyproject.toml`;
  use uv to update its committed `uv.lock`.
- Production memory and timeout values must be captured from the legacy
  functions and supplied in `PRODUCTION_DEPLOYMENT_ENV`; synthesis rejects missing
  values rather than selecting migration defaults.
- See `docs/aws-infrastructure.md` for validation, initial rollout, access,
  recovery, and cleanup boundaries.

## Data & Storage
- **Transcripts**: Stored in S3 at `transcripts/{video_id}.json` when configured.
- **Tasks**: Stored in the DB (`tasks` table) and polled via `/v2/internal/tasks`.
- **Queues**: SQS for AI note generation and AI summaries.

## Configuration (Common)
- Internal API access: `VIDWIZ_INTERNAL_API_BASE_URL`, `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`
- Helpers: `VIDWIZ_INTERNAL_API_BASE_URL` or `--api-url` (base), `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`, `--timeout`
- S3 access: `S3_TRANSCRIPT_BUCKET_NAME`, AWS credentials
- LLM provider: OpenRouter (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`)
