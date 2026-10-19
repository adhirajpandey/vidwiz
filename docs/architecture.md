# VidWiz Architecture

## Purpose
Provide a system-level view of how VidWiz components interact. Subsystem details live in their own docs.

## System Overview
- **Clients**: Web app (React), Chromium extension, and mobile automations (MacroDroid/Shortcuts).
- **Backend**: FastAPI service exposing public `/v2` and admin-only `/v2/internal` endpoints.
- **Workers**: Helpers for transcript, metadata, and title resolution; Lambdas for AI moments and AI summaries.
- **Storage**: PostgreSQL in deployed environments; SQLite by default in local dev.
- **Object store**: S3 for transcript JSON when `S3_TRANSCRIPT_BUCKET_NAME` and AWS credentials are configured.
- **Queues**: SQS for AI moment jobs (app + dispatcher) and overview jobs (app).
- **AWS infrastructure**: The production transcript bucket, queues, Lambdas,
  logs, event sources, and runtime roles are defined by the Python CDK app in
  `infra/` as `vidwiz-v3-stack`.

## Core Flows (High Level)
- **Capture**: Clients post `POST /v2/captures` with a video or a title, a time, an optional note, and an AI flag. Backend upserts the video, saves it to the user's library, schedules transcript/metadata tasks, and merges captures within 10 seconds of an existing moment. Title-only captures resolve through a `resolve_title` task.
- **Conversation start**: Starting Wiz chat also upserts the video and schedules transcript/metadata tasks.
- **Transcript/metadata/titles**: Helpers poll `/v2/internal/tasks`, fetch data, and submit results. A stored transcript fills the quotes of the video's moments. Transcript JSON is stored in S3 when configured; the video's `transcript_status` becomes `ready` either way, or `unavailable` when fetching fails for good.
- **AI moments**: Moments with an AI request are charged and queued to SQS once a transcript exists (at capture, or when the dispatcher collects pending moments after the transcript upload). The AI moment Lambda writes back via internal API. AI status is explicit on each moment.
- **Wiz chat**: Transcript-only grounding through OpenRouter. `WIZ_MODEL` selects the model and defaults to `minimax/minimax-m2.5`. If the transcript is not ready, chat returns `202 Accepted` and waits for processing.
- **Overviews + Wiz questions**: When the API stores a transcript it marks the
  overview `queued` and sends one structured generation that returns the
  summary, timestamped key points, and three starter questions. The worker
  saves it (`ready`) or reports `failed`; a failed overview can be retried for
  free. `SUMMARY_MODEL` selects the model.
- **Job states**: Every background job ends in an explicit state on its record
  (`transcript_status`, `overview_status`, a moment's `ai_status`). Workers
  report their own failures; a sweep fails jobs whose report never arrived.

## Auth Boundaries
- **JWT**: Required for most `/v2` endpoints.
- **Extension auth sync**: Web app login/logout can sync JWT to the extension via Chrome external messaging.
- **Personal API tokens**: Hashed, named, revocable tokens accepted only by capture endpoints (mobile automations and other capture clients).
- **Guest sessions**: `X-Guest-Session-ID` header enables Wiz chat without a JWT.
- **Admin token**: Required for `/v2/internal` endpoints.
  - Helpers/Lambdas use this token for polling tasks and writing results.

## Operational Notes
- The runtime-generated OpenAPI schema (`/openapi.json`) and Swagger UI
  (`/docs`) are available in every environment. They include internal route
  definitions, but the routes continue to enforce admin authentication.
- `DB_URL` defaults to SQLite if not provided.
- Transcript storage and Wiz chat require S3 credentials and bucket configuration.
- Wiz chat also requires `OPENROUTER_API_KEY`; without it, chat requests error.
- AI moments use `AI_NOTE_MODEL`, which defaults to `z-ai/glm-5.3-flash`.
- If S3 is not configured, transcripts are not persisted even though `transcript_status` may be `ready`, and Wiz chat will fail to load transcript data.
- Production AWS changes are deployed only by a manual workflow dispatch from
  `main`. GitHub uses
  branch-scoped OIDC rather than permanent AWS access keys.

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
     +--> DB (users, videos, moments, library, tasks, conversations)
     +--> SQS (AI moment/summary jobs)
             |
             v
         AI Moment/Summary Lambdas
```

The production AWS path is:

```text
GitHub OIDC -> VidwizGitHubDeployRole -> CDK bootstrap roles -> vidwiz-v3-stack
                                                               |
                         +-------------------------------------+----------+
                         |                                     |          |
                  transcript S3 -> dispatcher             note SQS   summary SQS
                                                               |          |
                                                          note Lambda summary Lambda
```
