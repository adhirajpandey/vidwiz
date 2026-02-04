# VidWiz Backend

## Purpose
Describe the FastAPI backend at a high level: core modules, data model, and how requests and async work are handled.

## Scope
- API structure, routing, and request validation.
- Domain services and data flow.
- Auth/authorization rules (JWT, long-term tokens, guest sessions).
- Async tasking and worker integration.

## Components
### App Entry + Config
- **App factory**: `backend/src/main.py` builds the FastAPI app, middleware, and router registrations.
- **ASGI entry**: `backend/wsgi.py` exposes the app for deployment.
- **Settings**: `backend/src/config.py` loads env configuration (DB, JWT, OAuth, AWS, SQS).

### Core Domains
Each domain follows a consistent pattern: `models.py`, `schemas.py`, `service.py`, `router.py`, `dependencies.py`.
- **Auth** (`backend/src/auth`): user accounts, JWT issuance, long-term tokens, Google OAuth.
- **Videos** (`backend/src/videos`): video records, metadata, transcript readiness, summary.
- **Notes** (`backend/src/notes`): timestamped notes; AI note trigger logic.
- **Conversations** (`backend/src/conversations`): Wiz chat, transcript-based responses, quotas.
- **Internal** (`backend/src/internal`): admin-only task polling and result submission.

### Data Layer
- **SQLAlchemy**: `backend/src/database.py` defines engine + session + base.
- **Models**:
  - `User`, `Video`, `Note`, `Conversation`, `Message`, `Task`.
- **Storage**: transcripts are stored in S3; relational data remains in DB.
- **Key relationships**:
  - `notes.video_id` references `videos.video_id` (string ID, not numeric PK).
  - `messages.conversation_id` references `conversations.id`.

### Auth & Viewer Context
- **JWT access tokens**: required for most `/v2` endpoints.
- **Long-term tokens**: issued via `/v2/auth/tokens`; accepted for note creation.
- **Guest sessions**: conversations can be accessed by `X-Guest-Session-ID` when no JWT is present.
- **Admin token**: required for `/v2/internal` endpoints.
- **Viewer resolution**: `get_viewer_context` prioritizes JWT (non-long-term), otherwise guest session ID.

### Request Validation & Error Shape
- **Pydantic schemas** validate request payloads and path/query params:
  - `video_id` is normalized from raw ID or URL; playlists are rejected.
  - `timestamp` must contain `:` and at least two digits.
  - `message` must be non-empty.
  - `metadata` and `transcript` payloads are shape-checked.
- **Errors** are standardized via `APIError` with `ErrorResponse` payloads.

## Key Flows
### 1) Auth
- `/v2/auth/register`, `/v2/auth/login`, `/v2/auth/google` for authentication.
- JWTs are signed with `SECRET_KEY` and include user metadata.
- Long-term tokens are created via `/v2/auth/tokens` and accepted for note creation.
- `/v2/users/me` exposes profile data; `/v2/users/me` (PATCH) updates name and AI note preference.

### 2) Notes + Videos
- Notes are created at `/v2/videos/{video_id}/notes`.
- Video ID is normalized and validated (YouTube ID or URL; playlists rejected).
- Video is upserted if missing and tasks are scheduled to fetch metadata/transcript.
- Notes are tied to the authenticated user (or long-term token user).
- `/v2/videos/{video_id}` requires a valid JWT; current implementation does not scope the lookup to the user's notes.
- `/v2/videos/{video_id}/stream` accepts JWT or guest session; authenticated requests are scoped to videos that have notes for the user.

### 3) Metadata/Transcript Tasks
- Tasks are stored in the `tasks` table with status and retry info.
- Internal workers poll `/v2/internal/tasks?type=transcript|metadata` with timeouts and polling parameters derived from constants.
- Results are submitted to `/v2/internal/tasks/{id}/result` and validated by task type.
- Transcript JSON is stored in S3; DB flags `transcript_available`.
- Metadata is stored directly on the `videos` record.
- Task polling uses row locking when supported (non-SQLite) to avoid duplicate work.

### 4) AI Notes
- If note text is empty and user has AI notes enabled, backend pushes a job to SQS.
- AI note trigger only fires when transcript is already available.
- AI note Lambda reads transcript from S3 and updates the note via internal API.
- Internal API exposes `/v2/internal/videos/{video_id}/ai-notes` to list eligible notes.

### 5) Wiz Conversations
- Conversations are created for a video and viewer (user or guest).
- Server loads transcript from S3 and streams Gemini responses via SSE.
- `prepare_chat` enforces daily quota and ensures transcript availability.
- If transcript is missing, API returns `202 Accepted` with `processing` status.
- Daily quotas are computed from UTC midnight and count user-role messages.

## Interfaces / Integration Points
- **Public API**: `/v2` endpoints for clients.
- **Internal API**: `/v2/internal` endpoints for trusted workers.
- **S3**: transcript storage used by chat and AI notes.
- **SQS**: AI note queue.
- **Google OAuth**: ID token verification.
- **LLM Providers**: Gemini (chat), Gemini/OpenAI (AI notes).

## Data / State (High-Level)
- **Users**: identity, profile data, AI notes toggle, long-term token.
- **Videos**: metadata JSON, transcript status, summary.
- **Notes**: timestamped notes with AI-generated flag.
- **Tasks**: async work queue for transcript/metadata.
- **Conversations/Messages**: chat history per video.

## Operational Notes
- API docs are disabled outside local/staging environments.
- SQLite is supported locally; Postgres is used in Docker/deploy.
- Internal API requires `ADMIN_TOKEN`.
- Errors are normalized via `APIError` and Pydantic error payloads.
- Request validation is handled by Pydantic schemas with explicit validators for timestamps, IDs, and payload shapes.
- Transcripts are stored in S3 only when S3 credentials and bucket are configured.

## API Surface (By Domain)
### Auth
- `POST /v2/auth/register`: create user.
- `POST /v2/auth/login`: email/password login.
- `POST /v2/auth/google`: Google ID token login.
- `POST /v2/auth/tokens`: create long-term token (JWT only).
- `DELETE /v2/auth/tokens`: revoke long-term token.
- `GET /v2/users/me`: current profile.
- `PATCH /v2/users/me`: update name + AI notes toggle.

### Videos
- `GET /v2/videos`: list/search videos for the authenticated user.
- `GET /v2/videos/{video_id}`: fetch video by ID (JWT required).
- `GET /v2/videos/{video_id}/stream`: SSE stream of video readiness.

### Notes
- `GET /v2/videos/{video_id}/notes`: list notes for a video (JWT only).
- `POST /v2/videos/{video_id}/notes`: create note (JWT or long-term token).
- `PATCH /v2/notes/{note_id}`: update note (JWT only).
- `DELETE /v2/notes/{note_id}`: delete note (JWT only).

### Conversations
- `POST /v2/conversations`: create conversation (JWT or guest session).
- `GET /v2/conversations/{id}`: read conversation.
- `GET /v2/conversations/{id}/messages`: list messages.
- `POST /v2/conversations/{id}/messages`: stream response (SSE).

### Internal
- `GET /v2/internal/tasks`: poll for transcript/metadata tasks.
- `POST /v2/internal/tasks/{id}/result`: submit task result.
- `GET /v2/internal/videos/{video_id}/ai-notes`: fetch AI note candidates.
- `POST /v2/internal/videos/{video_id}/transcript`: store transcript (upsert video).
- `POST /v2/internal/videos/{video_id}/metadata`: store metadata (upsert video).
- `POST /v2/internal/videos/{video_id}/summary`: store summary (upsert video).
- `GET /v2/internal/videos/{video_id}`: fetch video (internal view).
- `PATCH /v2/internal/notes/{note_id}`: update note (internal).

## Streaming Behavior (SSE)
- **Video readiness**: `/v2/videos/{id}/stream` emits `snapshot`, `update`, and `done` events when metadata + transcript + summary are all ready (60s timeout).
- **Chat responses**: `/v2/conversations/{id}/messages` streams chunks as `data: {\"content\": ...}` and terminates with `data: [DONE]`.

## Open Questions
- Should task scheduling move out of the main DB as scale increases?
- Is summary generation required in the core flow or optional?

## Interaction Overview (ASCII)
```
Clients (Web/Extension/Mobile)
  |
  v
FastAPI /v2
  |
  +--> PostgreSQL/SQLite (users, videos, notes, conversations, tasks)
  +--> SQS (AI note requests)
  |
  v
Internal /v2/internal (admin token)
  |
  +--> S3 (transcripts)
  +--> Task updates (metadata/transcript)

Workers
  - Transcript/Metadata helpers <-> Internal API
  - AI Note Lambda <-> Internal API (updates notes)
  - AI Summary Lambda <-> Internal API (updates videos)
```
