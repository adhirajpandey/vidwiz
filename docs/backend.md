# VidWiz Backend

## Purpose
Describe the FastAPI backend: structure, auth rules, and the request/worker lifecycle.

## Structure
- **App factory**: `backend/src/main.py` configures the FastAPI app and routers.
- **Settings**: `backend/src/config.py` (DB, JWT, OAuth, AWS, queues). Conversation settings live in `backend/src/conversations/config.py` (Gemini, quotas, S3).
- **Domains**: `auth`, `videos`, `notes`, `conversations`, `internal` follow `models/schemas/service/router/dependencies`.
- **ASGI entrypoint**: `backend/wsgi.py`.

## Auth & Access
- **JWT**: Required for most `/v2` endpoints.
- **Long-term tokens**: Only allowed for `POST /v2/videos/{video_id}/notes`.
- **Guest sessions**: `X-Guest-Session-ID` enables Wiz chat without a JWT.
- **Admin token**: Required for `/v2/internal/*` endpoints.
- **Secrets**: `SECRET_KEY` is required for JWT issuance and verification; missing it causes auth endpoints to return errors.
- **JWT expiry**: `JWT_EXPIRY_HOURS` controls JWT lifetime (default 24 hours).
- **Token payloads**: JWTs include `user_id`, `email`, `name`, `profile_image_url`, `exp`. Long-term tokens include `user_id`, `email`, `type=long_term`, and `iat` (no expiry).

## Validation Rules (Selected)
- **video_id**: Normalized from YouTube IDs or URLs; supports `youtube.com/watch`, `/shorts/`, `/live/`, `/embed/`, and `youtu.be`. Playlist URLs are rejected.
- **timestamp**: Must include `:` and at least two digits.
- **Note text**: Empty/whitespace text is normalized to `null`.
- **Chat message**: Must be non-empty after trimming.
- **Transcript payload**: Items must be dicts containing at least `text`.

## Key Behavior
- **Video lookup**: `GET /v2/videos/{video_id}` is JWT-only but is not scoped to the user; it returns the video if it exists.
- **Video list**: `GET /v2/videos` returns only videos that have notes for the authenticated user (join on notes).
- **Video search**: `q` is trimmed; queries shorter than 2 chars are treated as empty. Sort keys: `created_at_desc|created_at_asc|title_asc|title_desc`. `per_page` defaults to 10, max 50.
- **Video stream**: `GET /v2/videos/{video_id}/stream` requires JWT or guest session. The video is not user-scoped for either viewers or guests.
- **Notes**: List/edit/delete require JWT; create accepts JWT or long-term token.
- **Task scheduling**: Creating a note or conversation upserts the video and schedules transcript/metadata tasks when missing.
- **AI notes**: Enqueued only when note text is empty, AI notes are enabled, and the transcript is already available.
  - Enqueue uses `SQS_AI_NOTE_QUEUE_URL` if configured.
- **Wiz quotas**: Daily message limits enforced separately for users and guests via `WIZ_USER_DAILY_QUOTA` and `WIZ_GUEST_DAILY_QUOTA`.

## Async + Workers Integration
- **Tasks**: Metadata/transcript tasks are stored in the `tasks` table and polled via `/v2/internal/tasks`.
- **Task polling**: `/v2/internal/tasks?type=transcript|metadata` blocks up to a configurable timeout and returns `204` when no work is available.
- **Task lifecycle**: On claim, a task is marked `in_progress`, `started_at` is set, and `retry_count` increments. Stale `in_progress` tasks can be reclaimed after a timeout.
- **Transcript storage**: Transcripts are written to S3 when AWS credentials and bucket are configured; `transcript_available` is still set even if S3 is not configured.
- **Wiz chat**: Requires S3 transcript access and `OPENROUTER_API_KEY`. If transcript is not ready, `POST /v2/conversations/{id}/messages` returns `202 Accepted` with `status=processing`. If the transcript flag is set but S3 data is missing, the request errors with `Transcript data missing`.

## Streaming (SSE)
- **Video readiness**: `/v2/videos/{id}/stream` emits `snapshot`, `update`, and `done` when metadata, transcript, and summary are all ready (timeout 60s).
- **Wiz responses**: `/v2/conversations/{id}/messages` streams chunked `data: {"content": ...}` and ends with `data: [DONE]`.

## Error Shape
- API errors are normalized to `{"error": {"code", "message", "details"}}` for handled exceptions.
## Response Conventions
- Datetimes are serialized as `YYYY-MM-DDTHH:MM:SS±HHMM` (local timezone offset).

## Data Model (Core Tables)
- **users**: Email/password or Google login; stores `long_term_token` and `profile_data`.
- **videos**: Metadata JSON, `transcript_available`, and optional `summary`.
- **notes**: Timestamped notes tied to `videos.video_id` and a `user_id` (user foreign key is not enforced at the DB layer).
- **conversations/messages**: Threaded chat history per video; supports guest sessions.
- **tasks**: Internal work queue with `task_details`, `worker_details`, and retry metadata.

## Public API Surface (By Domain)
### Auth
- `POST /v2/auth/register`, `POST /v2/auth/login`, `POST /v2/auth/google`
- `POST /v2/auth/tokens`, `DELETE /v2/auth/tokens`
- `GET /v2/users/me`, `PATCH /v2/users/me`

### Videos
- `GET /v2/videos` (list/search)
- `GET /v2/videos/{video_id}`
- `GET /v2/videos/{video_id}/stream`

### Notes
- `GET /v2/videos/{video_id}/notes`
- `POST /v2/videos/{video_id}/notes`
- `PATCH /v2/notes/{note_id}`
- `DELETE /v2/notes/{note_id}`

### Conversations
- `POST /v2/conversations`
- `GET /v2/conversations/{id}`
- `GET /v2/conversations/{id}/messages`
- `POST /v2/conversations/{id}/messages` (SSE)

### Internal
- `GET /v2/internal/tasks`
- `POST /v2/internal/tasks/{id}/result`
- `GET /v2/internal/videos/{video_id}/ai-notes`
- `POST /v2/internal/videos/{video_id}/transcript`
- `POST /v2/internal/videos/{video_id}/metadata`
- `POST /v2/internal/videos/{video_id}/summary`
- `GET /v2/internal/videos/{video_id}`
- `PATCH /v2/internal/notes/{note_id}`

## Operational Notes
- OpenAPI docs are enabled only in `local` and `staging` environments.
- SQLite is the default when `DB_URL` is not set; Postgres is used in deployed environments.
- CORS allows all origins with credentials enabled; browsers will reject credentialed requests with wildcard origins.
- Rate limiting uses SlowAPI with an in-memory store by default and IP-only keys.
  - Env vars: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CONVERSATIONS`, `RATE_LIMIT_VIDEOS`.
  - `/v2/internal/*` endpoints are exempt.
