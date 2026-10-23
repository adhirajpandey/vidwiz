# VidWiz Backend

## Purpose
Describe the FastAPI backend: structure, auth rules, and the request/worker lifecycle.

## Structure
- **App factory**: `backend/src/main.py` configures the FastAPI app and routers.
- **Settings**: `backend/src/config.py` (DB, JWT, OAuth, AWS, queues, S3, OpenRouter, Wiz quotas).
- **Domains**: `auth`, `videos`, `moments`, `library`, `conversations`, `internal` follow `models/schemas/service/router/dependencies`.
- **Transcripts**: `backend/src/transcripts.py` stores and loads transcript JSON in S3 and extracts moment quotes.
- **Migrations**: Alembic in `backend/migrations`. Revision `0001` reproduces the
  pre-v3 production schema; existing databases are stamped at `0001` once, then
  upgraded. The Compose `migrate` service runs `alembic upgrade head` before the API starts.

## Auth & Access
- **JWT**: Required for most `/v2` endpoints.
- **Personal API tokens**: Accepted only by capture endpoints (`POST /v2/captures` and the legacy extension route). Tokens are opaque `vw_…` strings stored as SHA-256 hashes in `api_tokens`, with a name, hint, last-used time, and revocation. Long-term JWTs from before v3 were hashed into the same table and keep working.
- **Guest sessions**: `X-Guest-Session-ID` enables Wiz chat without a JWT.
- **Admin token**: Required for `/v2/internal/*` endpoints.
- **Signup defaults**: New users created via `POST /v2/auth/register` start with `profile_data.ai_moments_default = true`. Captures without an explicit `ai` flag use this setting.
- **Secrets**: `SECRET_KEY` is required for JWT issuance and verification; the server does not start when it is missing or empty.
- **JWT expiry**: `JWT_EXPIRY_HOURS` controls JWT lifetime (default 168 hours, or 7 days).
- **Token payloads**: JWTs include `user_id`, `email`, `name`, `profile_image_url`, `exp`. A JWT with `type=long_term` is never accepted as a session; it is checked by hash like any API token.

## Validation Rules (Selected)
- **video_id**: Normalized from YouTube IDs or URLs; supports `youtube.com/watch`, `/shorts/`, `/live/`, `/embed/`, and `youtu.be`. Playlist URLs are rejected. An invalid ID in a route path returns `422 VALIDATION_ERROR`, after any auth check.
- **Capture time (`at`)**: Seconds, `m:ss`, or `h:mm:ss`; never negative.
- **Moment text**: Empty/whitespace notes are normalized to `null`.
- **Chat message**: Must be non-empty after trimming.
- **Transcript payload**: Items must be dicts containing at least `text`.

## Key Behavior
- **Video lookup**: `GET /v2/videos/{video_id}` is JWT-only but is not scoped to the user; it returns the video if it exists.
- **Task scheduling**: Capturing, saving, or starting a conversation upserts the video and schedules transcript/metadata tasks when missing.
- **Wiz quotas**: Daily message limits enforced separately for users and guests via `WIZ_USER_DAILY_QUOTA` and `WIZ_GUEST_DAILY_QUOTA`.
- **Wiz token budget**: `WIZ_MAX_TOKENS` (default 8192) controls the max completion tokens per Wiz response, including model reasoning. The larger ceiling accommodates structured evidence on long transcripts; explicit environment overrides remain authoritative.

### Moments and captures
- A moment is a capture on a video: `at_seconds`, a `quote` (transcript lines
  overlapping 10 seconds before to 5 seconds after the capture, capped at
  350 characters, with
  `quote_start_seconds`), an optional `ai_text`, and an optional user `note`.
- **`POST /v2/captures`** accepts `video` (URL or ID) or `title` (+ optional
  `channel`), `at`, `note`, `ai`, and `source` (`phone`, `extension`, `web`,
  `api`). It returns `{moment, merged}` with `201`, or `200` when merged.
- **Dedupe**: a capture within 10 seconds of the user's existing moment on the
  same video merges into it. A new note is appended on a new line. Merging is
  never charged again.
- **Title captures**: a title matching a video already in the user's library
  (case-insensitive) resolves immediately. Otherwise the moment is saved with
  `video_id = null`, `resolve_status = resolving`, and a `resolve_title` task.
  The title helper searches YouTube with yt-dlp, preferring a matching channel,
  then an exact title. On success the moment gets its video (or merges into a
  nearby moment); after the final failed retry it becomes `unresolved`.
- **AI status** is explicit: `not_requested`, `waiting_transcript`, `queued`,
  `ready`, `failed`, `no_transcript`, or `insufficient_credits`.
  - With a transcript, a request charges `AI_MOMENT_COST` once per moment and
    queues the job (`queued`). Without credits the moment is kept as
    `insufficient_credits`.
  - Without a transcript the moment waits (`waiting_transcript`). After the
    transcript upload the dispatcher calls
    `POST /v2/internal/videos/{video_id}/pending-moments`, which charges and
    queues those moments. A transcript task that fails for the last time marks
    them `no_transcript`.
  - If sending the job to SQS fails, the moment becomes `failed`. Requesting AI
    again (`POST /v2/moments/{id}/ai`) does not charge again.
  - The worker stores its result through `PUT /v2/internal/moments/{id}/ai`;
    `ai_text: null` marks a queued generation `failed` and leaves a ready line
    alone.
  - The sweep marks lines queued for over 30 minutes `failed`, for jobs whose
    result never arrived.
- **Quotes** are filled at capture when the transcript exists, and for all of a
  video's moments without quotes when its transcript arrives. Filling or
  recomputing quotes preserves `updated_at` and the library order.
- **Saved passages**: `POST /v2/moments/passages` keeps a cited range as a
  moment whose quote is the transcript text in that range. No AI, no credits;
  merges like a capture.
- **Ambiguous titles**: when the title helper cannot pick one video
  confidently, the moment becomes `unresolved` with `resolve_candidates`;
  `POST /v2/moments/{id}/resolve` with one of their ids completes it (or merges
  it into a nearby moment), keeping any pending AI request.
- **Export**: `GET /v2/videos/{video_id}/export.md` and
  `GET /v2/library/export.md` return Markdown with timestamped YouTube links.
- **Legacy route**: `POST /v2/videos/{video_id}/notes` keeps the published 2.x
  extension working (`timestamp`, `text`, `video_title`). An empty `text`
  requests AI if the user setting allows it. Remove it once the 3.x extension
  is live.

### Search
- Stored transcripts are split into ~45-second passages in `transcript_chunks`
  (written whenever a transcript is stored; `python -m src.management.backfill
  chunks [--missing-only]` fills existing videos from S3).
- Moments and passages have generated `tsvector` columns (English stemming) with
  GIN indexes. The user's note and AI line weigh more than the quote.
- `GET /v2/search?q=` requires every term as a word prefix and ranks moments
  (boosted ×1.5) and passages from saved videos together. Results carry a `kind`
  discriminator (`moment` or `passage`), the video, a start time, and a snippet
  split into highlighted and plain parts. With no full-text match, trigram word
  similarity (threshold 0.45) tolerates typos and the response says
  `match: fuzzy`; `none` means nothing matched. `video_id` limits the search to
  one video.

### Library Ask
- `POST /v2/conversations` with `{"scope": "library"}` (no `video_id`) starts a
  library conversation for a signed-in user. It is free within the daily
  message quota.
- Each question: `ASK_QUERY_MODEL` (default `z-ai/glm-5.3-flash`) plans it as
  search terms and synonyms, plus an optional period of local capture dates
  ("this week", "yesterday") and whether it has a topic. The message's optional
  `time_zone` (an IANA name; the web app sends the browser's, and unknown or
  missing zones use UTC) decides today's date and day boundaries. Full-text
  search in any-term mode gathers up to `ASK_CANDIDATES` (48) moments and
  passages; Jev (`JEV_MODEL`, a pinned dated
  version, through OpenRouter's decisions endpoint) scores each candidate's
  relevance in parallel batches; up to `ASK_MAX_SOURCES` (8) candidates at or
  above `JEV_RELEVANCE_THRESHOLD` (0.5) become the answer's sources. With
  `JEV_ENABLED=false` or a Jev failure, the full-text order is used.
- A question only about a period ("Summarize what I saved this week") skips
  search and Jev: its sources are the newest moments captured in that period,
  up to `ASK_TIME_RANGE_MAX_SOURCES` (25). A period with a topic searches only
  moments captured then, since transcript passages have no capture time. With
  no sources, the answer says it found no matching moments from that period,
  and it never counts moments, since sources can be capped. Moment sources
  carry their local capture date, and the saved answer's metadata records
  `time_range` (`since`, `until`, `time_zone`).
- Answers use the same structured block stream as video chat. Source ids are
  `m<moment id>` or `c<chunk id>`, and resolved citations carry `video_id`
  (null in video conversations). Each question logs one `Library Ask
  retrieval:` line with the model, candidate count, kept count, threshold, and
  top scores.

### Conversations
- `GET /v2/conversations` lists the user's conversations that have at least one
  question, latest first, with the first question as a title. Filter by
  `scope` or `video_id` to resume a chat.

### Transcripts and overviews
- **Transcript status** (`videos.transcript_status`) is explicit: `pending`,
  `ready`, or `unavailable`. Storing a transcript makes it `ready`. A
  transcript task that fails for the last time, or succeeds without segments,
  makes it `unavailable`; a later capture schedules a new task and sets it back
  to `pending`.
- **Overview status** (`videos.overview_status`, changed at
  `overview_status_at`):

  ```
  pending ──transcript ready──▶ queued ──worker saves──▶ ready
     │                            │  ▲
     │                            │  └── retry, backfill ── failed, ready
     │                            └── worker gives up, sweep ──▶ failed
     └── transcript unavailable ──▶ no_transcript ── transcript ready ──▶ queued
  ```

  - The API is the only place that queues an overview: when it stores a
    transcript (from `pending`, `no_transcript`, or `failed`), on a retry, and
    in the backfill. If sending the job fails, the overview becomes `failed`.
  - The worker saves through `POST /v2/internal/videos/{id}/summary`, which
    marks it `ready`, or reports `POST /v2/internal/videos/{id}/overview/failed`,
    which fails only a queued overview.
  - `POST /v2/videos/{video_id}/overview/retry` (signed in, free) queues a
    failed overview again.
  - The sweep marks overviews queued for over two hours `failed`.
  - Summaries from before key points count as `ready`; the backfill rewrites
    them.
- `GET /v2/videos/{video_id}/transcript` returns `status` (the transcript
  status) and, when `ready`, the segments. JWT or guest session.
- **Models are recorded on every AI output**: `moments.ai_model` for AI
  lines, `miscellaneous_data.overview_model` and `overview_generated_at` for
  overviews (`VideoRead.overview_model`), and a `models` object in saved
  answer metadata (`model`, plus `query_model` and `relevance_model` for
  library answers; null when that step was skipped).
- `VideoRead.key_points` exposes the overview's key points
  (`text`, `start_seconds`, `end_seconds`), stored in
  `miscellaneous_data.key_points`. Writes that omit key points keep the
  existing ones.

### Library
- `library_items` records saved videos per user. Capturing a moment or sending
  a chat message saves the video. `PUT /v2/library/{video_id}` saves
  explicitly; `DELETE` removes the item and keeps its moments.
- `GET /v2/library` returns `moment_count`, `transcript_status`,
  `overview_status`,
  `added_at`, and `last_activity_at` (latest of added, opened, moment update,
  or chat message). Sorts: `activity_desc` (default), `added_desc`,
  `title_asc`, `title_desc`. `q` (2+ characters) filters titles literally.

## Async + Workers Integration
- **Tasks**: Metadata, transcript, and title-resolution tasks are stored in the `tasks` table and polled via `/v2/internal/tasks`.
- **Task polling**: `/v2/internal/tasks?type=transcript|metadata|resolve_title` blocks up to a configurable timeout and returns `204` when no work is available.
- **Task lifecycle**: On claim, a task is marked `in_progress`, `started_at` is set, and `retry_count` increments. Stale `in_progress` tasks can be reclaimed after a timeout.
- **Transcript storage**: Transcripts are written to S3 when `S3_TRANSCRIPT_BUCKET_NAME` is configured, using the application's required AWS credentials; the transcript is still marked `ready` when the bucket is not configured.
- **Sweep**: `python -m src.management.sweep --every 600` runs beside the API and fails jobs that stayed queued past the limits above.
  It also deletes conversations created over 7 days ago that have no
  messages. Opening Ask creates a conversation before the first question, so
  abandoned opens would otherwise pile up. Deleting one does not lock a paid
  video chat again: the unlock is the `wiz_chat` credits ledger entry for the
  video. A message saved during the sweep makes the delete fail on the
  messages foreign key, and the next pass tries again.
- **Backfills**: `python -m src.management.backfill chunks [--missing-only]` stores search passages; `python -m src.management.backfill overviews --limit N` queues up to N overviews that are missing, failed, or older than key points, most recently used videos first. `python -m src.management.backfill quotes` fills missing moment quotes on transcript-ready videos; use it for bulk imports whose moments arrive after their transcripts. Add `--all` to recompute existing quotes with the current window while preserving each moment's `updated_at`.
- **Wiz chat**: Requires S3 transcript access and `OPENROUTER_API_KEY`. If transcript is not ready, `POST /v2/conversations/{id}/messages` returns `202 Accepted` with `status=processing`. If the transcript flag is set but S3 data is missing, the request errors with `Transcript data missing`.

## Streaming (SSE)
- **Wiz responses**: `/v2/conversations/{id}/messages` emits JSON SSE data with a
  `type` discriminator: `block`, `done`, or `error`. Each `block` event contains
  one complete Markdown block in `text` and its resolved `citations`. `done`
  includes the persisted `message_id`; failures end with `error` and a safe
  `message`. There is no `[DONE]` sentinel. EOF without a terminal event is
  interruption.

### Wiz structured responses

OpenRouter receives a strict JSON schema for an ordered `parts` array of blocks.
Requests require a provider supporting structured outputs. FastAPI
incrementally frames complete JSON objects, validates them, resolves
references, and streams each block. It validates the full envelope and checks
successful model completion before saving. Malformed or truncated output ends
with an error. Already emitted blocks remain visible in the client but failed
partial assistant responses are not saved. The system prompt is fixed in
`backend/src/conversations/prompts.py`.

Wiz normalizes existing transcript segments at read time. IDs combine a SHA-256
transcript revision prefix with the original segment index. They remain stable
for the same transcript snapshot. Start times use `offset`; end times use
`offset + duration`. Missing duration uses the next later valid offset, or the
start time if none exists. Invalid timing leaves text in context without a
citable ID. Fractional seconds are preserved. S3 objects and workers are unchanged.

Message requests accept an optional `parts_version`, which must be `2`. The
model supplies `references` with `chunk_ids` and a nullable
`list_item_index`: null targets the whole Markdown block; an integer targets a
zero-based top-level list item, including its nested content. A Markdown parser
validates targets. Invalid targets and unknown source IDs are omitted and logged
without discarding the answer text. The prompt asks for one complete Markdown
element per block, but models often return a whole answer as one block. FastAPI
therefore splits each block into one block per top-level element, slicing the
original source lines so text is preserved exactly. References are re-targeted:
an integer `list_item_index` applies to the block's only list, and `null` applies
to the last non-heading element. References that cannot be placed (several lists,
index out of range, only headings) are dropped and counted by reason. Blocks with
several elements and link reference definitions are left whole, because splitting
would separate a definition from its uses; their references are dropped and
counted as `link_definitions`. Each split block is streamed, stored
and replayed as its own block.

After every response FastAPI logs one INFO line starting with
`Wiz structure:` with the model, `blocks_in`, `blocks_out`, `blocks_split`
(input blocks that needed splitting), distinct chunk IDs `referenced` by the
model and `kept` in the final citations, and `dropped_<reason>` counts. Grep it
with `docker logs vidwiz-app | grep "Wiz structure"`; `blocks_split` shows how
often the model ignores the structure rule.

Resolved citations contain `list_item_index` and `passages`, each with
`chunk_ids`, `start_seconds`, and `end_seconds`. Within each target, sources are
deduplicated and sorted; ranges merge with gaps up to 5 seconds and a combined
length up to 60 seconds. Individual longer captions are preserved. Separate
claims and distant passages remain separate. The model cannot supply timestamps.

Completed assistant parts are stored in message metadata with `parts_version: 2`
and `parts`. The `content` column contains text joined by blank lines. Message
reads expose typed `parts`. Messages saved before this format keep their stored
`text` and `citation` parts (`parts_version: 1`), and plain older messages
become one text part. Follow-up model context replays history as blocks and
discards IDs absent from the current transcript. Older text parts replay as
blocks without references; their standalone citations are not replayed, because
they have no block association. Stored citation timestamps remain unchanged when
a transcript is replaced.

## Wiz Starter Questions
- `VideoRead.suggested_questions` exposes only the validated question list; the
  complete `miscellaneous_data` object is not part of the public API.
- Videos without generated questions return `suggested_questions=null` and
  retain the existing metadata + transcript + summary readiness rules.
- The internal summary write accepts summary text plus nested miscellaneous
  data and shallow-merges it into the existing object. Unrelated top-level keys
  are preserved, duplicate top-level keys are overwritten, and nested objects
  are replaced rather than recursively merged.

## Error Shape
- API errors are normalized to `{"error": {"code", "message", "details"}}` for handled exceptions.
## Response Conventions
- Datetimes are serialized as `YYYY-MM-DDTHH:MM:SS±HHMM` (local timezone offset).

## Data Model (Core Tables)
- **users**: Email/password or Google login; stores `profile_data` (`ai_moments_default`) and `credits_balance`.
- **videos**: Metadata JSON, `transcript_status`, optional `summary`,
  `overview_status` and `overview_status_at`, and
  general-purpose `miscellaneous_data` JSON. Wiz starter questions are stored
  under `miscellaneous_data.suggested_questions`.
- **moments**: Captures tied to a user and (once resolved) a video, with explicit `ai_status`, `resolve_status`, and `source`, enforced by CHECK constraints.
- **library_items**: Saved videos per user (composite key `user_id, video_id`).
- **api_tokens**: Hashed personal API tokens.
- **conversations/messages**: Chat history with a `scope` of `video` (with `video_id`) or `library` (without); supports guest sessions.
- **tasks**: Internal work queue with `task_details`, `worker_details`, and retry metadata.

## Public API Surface (By Domain)
### Auth
- `POST /v2/auth/register`, `POST /v2/auth/login`, `POST /v2/auth/google`
- `GET /v2/auth/tokens`, `POST /v2/auth/tokens`, `DELETE /v2/auth/tokens/{token_id}`
- `GET /v2/users/me`, `PATCH /v2/users/me`

### Videos
- `GET /v2/videos/{video_id}`
- `GET /v2/videos/{video_id}/stream`
- `GET /v2/videos/{video_id}/transcript`

### Moments
- `POST /v2/captures`
- `GET /v2/moments` (recent moments across the library)
- `GET /v2/videos/{video_id}/moments`
- `PATCH /v2/moments/{moment_id}`, `DELETE /v2/moments/{moment_id}`
- `POST /v2/moments/{moment_id}/ai`
- `POST /v2/videos/{video_id}/notes` (legacy 2.x extension)

- `POST /v2/moments/passages`, `POST /v2/moments/{moment_id}/resolve`
- `GET /v2/videos/{video_id}/export.md`, `GET /v2/library/export.md`

### Library
- `GET /v2/library`
- `PUT /v2/library/{video_id}`, `DELETE /v2/library/{video_id}`

### Search
- `GET /v2/search`

### Conversations
- `GET /v2/conversations`
- `POST /v2/conversations`
- `GET /v2/conversations/{id}`
- `GET /v2/conversations/{id}/messages`
- `POST /v2/conversations/{id}/messages` (SSE)

### Internal
- `GET /v2/internal/tasks`
- `POST /v2/internal/tasks/{id}/result`
- `POST /v2/internal/videos/{video_id}/pending-moments`
  returns HTTP 409 while the transcript is `pending`, without charging credits
  or changing moments. It returns already-queued moments again without charging
  so dispatch retries can recover lost responses. The dispatcher retries as
  described in [Workers](workers.md).
- `POST /v2/internal/videos/{video_id}/transcript`
- `POST /v2/internal/videos/{video_id}/metadata`
- `POST /v2/internal/videos/{video_id}/summary`
- `GET /v2/internal/videos/{video_id}`
- `PUT /v2/internal/moments/{moment_id}/ai`

### Payments
- `GET /v2/payments/products`
- `POST /v2/payments/checkout`
- `POST /v2/payments/webhooks/dodo`

## Operational Notes
- The generated OpenAPI schema is available at `/openapi.json` and interactive
  Swagger UI is available at `/docs` in every environment. ReDoc is disabled.
- Swagger includes public, internal, and payment webhook routes. Protected
  operations still require their existing JWT, guest-session, or admin
  credentials.
- SQLite is the default when `DB_URL` is not set; Postgres is used in deployed environments.
- CORS allows all origins with credentials enabled and exposes `X-Request-ID`
  and `Retry-After` to browser clients; browsers will reject credentialed
  requests with wildcard origins.
- Rate limiting uses SlowAPI with an in-memory store by default and IP-only keys.
  - Env vars: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CONVERSATIONS`, `RATE_LIMIT_VIDEOS`.
  - `/v2/internal/*` endpoints are exempt.
- Prometheus metrics are exposed at `GET /v2/internal/metrics` and require the admin token.

## Logging
- API requests log a single structured entry with request/response metadata.
- `X-Request-ID` is generated if missing and echoed in responses.
- Request/response bodies are logged for JSON/text content types, redacted and truncated.
- Logging skips the metrics endpoint and Loki excludes `/v2/internal/tasks`.
- Log output includes endpoint name and source location when resolvable.
- Severity mapping: `INFO` for 2xx/3xx, `WARNING` for 4xx, `ERROR` for 5xx.
- Truncation defaults: 8KB for request bodies and 8KB for response bodies.
- Redaction applies to: `password`, `token`, `access_token`, `refresh_token`, `long_term_token`, `authorization`, `secret`, `api_key`, `key`, `cookie`, `set-cookie`, `session`, `csrf`, `jwt`.
- Default JSON fields include (when available):
  - `timestamp`, `level`, `logger`, `message`, `request_id`
  - `http_method`, `http_path`, `http_query`, `http_status`, `duration_ms`
  - `client_ip`, `user_agent`
  - `endpoint`, `endpoint_source`
  - `request_content_type`, `request_body`, `request_body_bytes`, `request_body_truncated`
  - `response_content_type`, `response_body`, `response_body_bytes`, `response_content_length`, `response_body_truncated`
- `client_ip` extraction precedence matches rate limiting: `X-Forwarded-For` (first IP), then `X-Real-IP`, then socket client host.
- Stdout is pretty-printed for readability; Loki receives JSON.
- Configure Loki via:
  - `LOKI_URL` (Grafana Cloud Loki push URL)
  - `LOKI_USERNAME`, `LOKI_PASSWORD`
  - Optional: `LOG_LEVEL`, `LOG_SERVICE_NAME`

## Startup Requirements
The server fails on startup if any of the following env vars are missing. `ENVIRONMENT`,
`SECRET_KEY`, `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`, and `GOOGLE_CLIENT_ID` must also be non-empty:
- `ENVIRONMENT`
- `SECRET_KEY`
- `VIDWIZ_INTERNAL_API_ADMIN_TOKEN`
- `GOOGLE_CLIENT_ID`
- `SQS_AI_NOTE_QUEUE_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `DODO_PAYMENTS_API_KEY`
- `DODO_PAYMENTS_WEBHOOK_KEY`
- `DODO_PAYMENTS_ENVIRONMENT`
- `DODO_PAYMENTS_RETURN_URL`
- `DODO_CREDIT_PRODUCTS`
