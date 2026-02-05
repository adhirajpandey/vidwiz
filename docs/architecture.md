# VidWiz Architecture

## Purpose
Provide a system-level view of how VidWiz components interact. Subsystem details live in their own docs.

## System Overview
- **Clients**: Web app (React), Chromium extension, and mobile automations (MacroDroid/Shortcuts).
- **Backend**: FastAPI service exposing public `/v2` and admin-only `/v2/internal` endpoints.
- **Workers**: Helpers + Lambdas for transcript/metadata fetching, AI notes, and AI summaries.
- **Storage**: PostgreSQL in deployed environments; SQLite by default in local dev.
- **Object store**: S3 for transcript JSON when `S3_BUCKET_NAME` and AWS credentials are configured.
- **Queues**: SQS for AI note jobs (app + dispatcher) and AI summary jobs (dispatcher).

## Core Flows (High Level)
- **Note creation**: Client posts a note (timestamp + optional text). Backend upserts the video and schedules transcript/metadata tasks.
- **Conversation start**: Starting Wiz chat also upserts the video and schedules transcript/metadata tasks.
- **Transcript/metadata**: Helpers poll `/v2/internal/tasks`, fetch data, and submit results. Transcript JSON is stored in S3 when configured; the DB `transcript_available` flag is set either way.
- **AI notes**: Empty-text notes from users with AI notes enabled are queued to SQS once a transcript is already available; the AI note Lambda writes back via internal API.
- **Wiz chat**: Transcript-only grounding via Gemini; if transcript is not ready, chat returns `202 Accepted` and waits for processing.
- **AI summaries**: Task dispatcher Lambda fires on transcript upload (S3) and enqueues summary generation.

## Auth Boundaries
- **JWT**: Required for most `/v2` endpoints.
- **Long-term tokens**: Accepted only for note creation (extension/mobile automations).
- **Guest sessions**: `X-Guest-Session-ID` header enables Wiz chat without a JWT.
- **Admin token**: Required for `/v2/internal` endpoints.
  - Helpers/Lambdas use this token for polling tasks and writing results.

## Operational Notes
- OpenAPI docs are enabled only in `local` and `staging` environments.
- `DB_URL` defaults to SQLite if not provided.
- Transcript storage and Wiz chat require S3 credentials and bucket configuration.
- Wiz chat also requires `GEMINI_API_KEY`; without it, chat requests error.
- If S3 is not configured, transcripts are not persisted even though `transcript_available` may be true, and Wiz chat will fail to load transcript data.

## Interaction Overview (ASCII)
```
Clients (Web/Extension/Mobile)
  |
  v
FastAPI API
  - Public /v2
  - Internal /v2/internal (admin token)
     |             |
     |             +--> S3 (transcripts)
     |
     +--> DB (users, videos, notes, tasks, conversations)
     +--> SQS (AI note/summary jobs)
             |
             v
         AI Note/Summary Lambdas
```
