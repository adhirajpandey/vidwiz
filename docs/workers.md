# VidWiz Workers

## Purpose
Describe background helpers and Lambdas used for transcript/metadata fetching and AI generation.

## Components
### Helpers (Long-Running)
- **Task helper**: `backend/workers/scripts/task-helper.py {transcript|metadata|resolve_title}`
  - Polls `/v2/internal/tasks?type=<task type>` with long-poll timeout (default 30s)
  - `transcript`: fetches transcripts via `youtube_transcript_api` (languages: `en`, `hi`)
    and renames each item's `start` to `offset`
  - `metadata`: fetches metadata via `yt_dlp`
  - `resolve_title`: finds the video for a title-only capture with a 5-result
    `yt_dlp` search, preferring a matching channel, then an exact title, then
    the first result. Sends `resolved: {video_id, title}`
  - Submits results to `/v2/internal/tasks/{id}/result`
  - CLI args: task type, `--timeout`, and optional `--api-url`
  - Internal API base URL resolution: `--api-url` -> `VIDWIZ_INTERNAL_API_BASE_URL`; exits on startup if neither is set

The production helper processes are owned by the `metadata-helper`,
`transcript-helper`, and `title-helper` Compose services; no repository workflow
or systemd unit manages parallel helper processes.

### Lambdas
- **AI Moment Lambda**: `backend/workers/lambdas/ai_note_worker`
  - `handler.py` parses SQS events and delegates to the functional
    `note_service.py` module.
  - Triggered by SQS messages containing moment jobs: `{ id, video_id, at_seconds, user_id }`
  - Fetches transcript from S3 with retry/backoff
  - Extracts context around the timestamp (buffer + surrounding segments)
  - Generates a one-line note with length constraints and retries on length mismatch
  - Uses OpenRouter via OpenAI-compatible API (`OPENROUTER_API_KEY`)
  - Stores the line via `PUT /v2/internal/moments/{id}/ai`
  - A missing transcript or empty context is permanent: the worker stores
    `ai_text: null`, which marks the moment `failed`
  - Generation or persistence failures fail the invocation so SQS retries the record
  - Reads the video title from `/v2/internal/videos/{video_id}`
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
  - For all video IDs: calls `POST /v2/internal/videos/{video_id}/pending-moments`, which charges and marks queued the moments waiting for the transcript, then batches them to the AI note SQS (batch size 10). Owners without credits get `insufficient_credits` instead
  - Uses `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`
  - Propagates unhandled dispatch failures so Lambda retry/DLQ handling can run

### Lambda Logging
Lambdas log processing milestones and failures with safe identifiers and
counts. They do not log complete events, request or response bodies, prompts,
transcripts, generated content, authorization values, or provider error
payloads.

### Lambda Infrastructure and Delivery
- `infra/` defines all three production functions, queues, the transcript
  bucket, event sources, log groups, and separate execution roles in
  `vidwiz-v3-stack`.
- Canonical function names are `vidwiz-v3-transcript-dispatcher`,
  `vidwiz-v3-ai-note-worker`, and `vidwiz-v3-ai-summary-worker`.
- `.github/workflows/deploy-aws-infrastructure.yml` validates and deploys production
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
- **Tasks**: Stored in the DB (`tasks` table) and polled via `/v2/internal/tasks`. Title tasks carry `{moment_id, title, channel}`.
- **Queues**: SQS for AI note generation and AI summaries.

## Configuration (Common)
- Internal API access: `VIDWIZ_INTERNAL_API_BASE_URL`, `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`
- Helpers: `VIDWIZ_INTERNAL_API_BASE_URL` or `--api-url` (base), `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`, `--timeout`
- S3 access: `S3_TRANSCRIPT_BUCKET_NAME`, AWS credentials
- LLM provider: OpenRouter (`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`)
- Summary model: `SUMMARY_MODEL` (default `qwen/qwen3.5-35b-a3b`)
- AI note model: `AI_NOTE_MODEL` (default `z-ai/glm-5.3-flash`)
