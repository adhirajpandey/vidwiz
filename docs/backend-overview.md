# VidWiz Backend Overview

## Architecture
- Flask app factory in `backend/vidwiz/app.py` wires blueprints, config, SQLAlchemy, CORS, and global error handlers.
- Route layer is thin and delegates to services in `backend/vidwiz/services/*.py` (core, users, videos, notes, tasks, wiz).
- Data access via SQLAlchemy models in `backend/vidwiz/shared/models.py`; services handle DB mutations and integrations.
- Async/background work: transcript + metadata tasks stored in DB (`Task`), processed via polling endpoints in `backend/vidwiz/routes/tasks_routes.py`, with helpers/lambdas in `backend/vidwiz/workers/`.
- Integrations: S3 transcript storage and SQS task enqueue in `backend/vidwiz/shared/utils.py`; Gemini chat in `backend/vidwiz/services/wiz_service.py`.
- SPA hosting: catch-all route serves `dist` assets from `backend/vidwiz/routes/frontend_routes.py`.

## Data Models (DB)
From `backend/vidwiz/shared/models.py`:
- `User`: email (unique), name, password_hash (nullable for OAuth), google_id, profile_image_url, long_term_token, profile_data (JSON), created_at.
- `Video`: video_id (unique), title, video_metadata (JSON), transcript_available, summary, timestamps.
- `Note`: belongs to `User` and `Video` via `user_id` + `video_id` FK, has timestamp, text, generated_by_ai.
- `Task`: task_type, status (enum), task_details JSON, worker_details JSON, retry_count, started/completed timestamps.
- `Conversation` + `Message`: Wiz chat history, linked by `conversation_id`, with role/content and optional metadata.

Relationships:
- `Video` ↔ `Note` (one-to-many).
- `User` ↔ `Note` (one-to-many).
- `Conversation` ↔ `Message` (one-to-many).

## Schemas (Pydantic)
From `backend/vidwiz/shared/schemas.py`:
- Request/response models for videos (`VideoCreate/Read/Update/Patch`), notes (`NoteCreate/Read/Update`), tasks (`TranscriptResult`, `MetadataResult`, `Task*Response`), users (`UserCreate/Login/Profile*`, token responses), Wiz (`WizInit*`, `WizChat*`, `WizConversation*`), search (`SearchResponse`), and Google login (`GoogleLoginRequest`).
- Input validation: YouTube ID normalization, timestamp format, email/password/name validation, etc.

## API Surface Overview
Blueprints registered under `/api` in `backend/vidwiz/app.py`.

### Core (`backend/vidwiz/routes/core_routes.py`)
- `GET /api/search` — Auth: JWT or long-term token. Video search for current user (query/pagination).

### Users (`backend/vidwiz/routes/user_routes.py`)
- `POST /api/user/signup` — Create user (email/password/name).
- `POST /api/user/login` — Email/password login -> JWT.
- `POST /api/user/token` — Create long-term token (auth required).
- `DELETE /api/user/token` — Revoke long-term token (auth required).
- `GET /api/user/profile` — Get profile (auth required).
- `PATCH /api/user/profile` — Update profile (auth required).
- `POST /api/user/google/login` — Google ID token login (no auth required).

### Videos (`backend/vidwiz/routes/video_routes.py`)
- `GET /api/videos/<video_id>` — Auth: JWT or long-term token. Fetch video.
- `GET /api/videos/<video_id>/notes/ai-note-task` — Auth: admin token. Fetch notes eligible for AI note generation.
- `PATCH /api/videos/<video_id>` — Auth: admin token. Update summary (Lambda use).

### Notes (`backend/vidwiz/routes/notes_routes.py`)
- `POST /api/notes` — Auth: JWT or long-term token. Create note; creates video and queues transcript/metadata tasks if missing.
- `GET /api/notes/<video_id>` — Auth required. List user notes for video.
- `DELETE /api/notes/<note_id>` — Auth required. Delete note.
- `PATCH /api/notes/<note_id>` — Auth: JWT or admin. Update note text / generated_by_ai.

### Tasks (`backend/vidwiz/routes/tasks_routes.py`)
- `GET /api/tasks/transcript` — Auth: JWT or admin. Long-poll for transcript task.
- `POST /api/tasks/transcript` — Submit transcript result.
- `GET /api/tasks/metadata` — Long-poll for metadata task.
- `POST /api/tasks/metadata` — Submit metadata result.

### Wiz (`backend/vidwiz/routes/wiz_routes.py`)
- `POST /api/wiz/init` — Queue transcript/metadata/summary tasks for a video.
- `GET /api/wiz/video/<video_id>` — Public status (transcript availability, metadata, summary).
- `POST /api/wiz/conversation` — Auth: JWT or guest. Create conversation.
- `POST /api/wiz/chat` — Auth: JWT or guest. SSE stream of Gemini response; enforces daily quota.

### Frontend catch-all (`backend/vidwiz/routes/frontend_routes.py`)
- `GET /` and `GET /<path>` serve `dist/` assets for the React app.
