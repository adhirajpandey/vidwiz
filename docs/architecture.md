# VidWiz Architecture

## Purpose
Explain how VidWiz components interact at a system level. This is a high-level view for engineers and coding agents; deeper subsystem details will live in separate docs.

## Scope
- What exists today in the repo.
- How web, extension, and mobile automations interact with the backend.
- Where async processing and storage live.

## Components
### Clients
- **Web app (Vite/React)**: Primary UI for video notes and conversations.
- **Browser extension (Chromium)**: Captures notes on YouTube pages and uses the same API.
- **Mobile automations**: Android (MacroDroid) and iOS (Shortcuts) capture notes while watching YouTube. These are lightweight API clients.

### Backend API
- **FastAPI service** (`backend/src`): Core API for auth, videos, notes, conversations.
- **Internal API** (`/v2/internal`): Admin-token protected endpoints used by workers to poll tasks and submit results.

### Data + Storage
- **PostgreSQL**: Primary DB in deployed environments (via SQLAlchemy).
- **SQLite**: Default local DB if `DB_URL` is not set.
- **S3**: Stores transcript JSON used by conversations and AI note generation.

### Async/Workers
- **Task queue in DB**: `tasks` table used for metadata/transcript fetch workflows.
- **Helper workers**:
  - Systemd helpers for transcript and metadata fetching.
  - AWS Lambda workers for AI notes and AI summaries.
- **SQS**: Enqueues AI note generation requests.

### External Services
- **Google OAuth**: Sign-in for web/extension clients.
- **LLM providers**:
  - **Gemini**: Used by conversation/chat responses.
  - **Gemini or OpenAI**: Used by AI note Lambda (provider chosen by env).

## Key Flows
### 1) Auth & Session
- Clients authenticate via email/password or Google OAuth.
- API issues JWT for standard sessions.
- Long-term tokens exist and are accepted for note creation (useful for extension/mobile automations).

### 2) Video + Note Creation
- Client sends a note with `video_id`, timestamp, and optional text.
- Backend upserts the video record (if missing) and schedules metadata/transcript fetch tasks.
- Note is stored in `notes` with user association.

### 3) Metadata & Transcript Fetch
- Backend creates task entries (DB) for transcript and metadata.
- Helper services poll `/v2/internal/tasks` for work.
- Results are submitted to `/v2/internal/tasks/{id}/result`.
- Transcript JSON is stored in S3; DB flags transcript availability.

### 4) AI Note Generation
- If a note is created without text and the user has AI notes enabled, the backend pushes a message to SQS.
- Lambda reads transcript from S3 and generates a note with Gemini or OpenAI.
- Lambda calls internal API to update the note.

### 5) Conversation/Chat
- Conversations are tied to a video and user (or guest session).
- Backend fetches transcript from S3 and streams Gemini responses.
- Rate limits are enforced per user or guest session.

### 6) AI Summary (Optional)
- A Lambda can generate video summaries and submit them via the internal API.
- Summary is stored on the `videos` record.

## Interfaces / Integration Points
- **Public API**: `/v2` endpoints consumed by web, extension, and mobile automations.
- **Internal API**: `/v2/internal` endpoints are admin-token protected and intended only for trusted workers.
- **Storage**: S3 for transcripts, DB for structured data.
- **Queues**: SQS for AI note jobs.

## Data / State (High-Level)
- `users`: accounts, OAuth data, profile data, long-term tokens.
- `videos`: YouTube video records, metadata, transcript availability, summaries.
- `notes`: timestamped notes tied to users and videos.
- `tasks`: async work items for transcript/metadata.
- `conversations` + `messages`: chat history per video.

## Operational Notes
- API docs are disabled outside local/staging environments.
- Deployed stack typically uses Postgres; local dev may use SQLite by default.
- Internal endpoints require a configured `ADMIN_TOKEN`.

## Open Questions
- Do we want to separate the internal task queue from the main DB in the future?
- Are AI summaries a required part of the current MVP flow or optional?

## Interaction Overview (ASCII)
```
Clients
  - Web App
  - Browser Extension
  - Mobile Automations (MacroDroid/Shortcuts)
        |
        v
FastAPI API
  - Public /v2
  - Internal /v2/internal
     |            |
     |            +--> S3 (transcripts)
     |
     +--> PostgreSQL/SQLite (users, videos, notes, tasks, conversations)
     +--> SQS (AI note requests)
             |
             v
        AI Note Lambda
             |
             v
        Internal API (update note)

Helpers (transcript/metadata) ---> Internal API (poll/submit)
AI Summary Lambda -------------> Internal API (submit summary)
```
