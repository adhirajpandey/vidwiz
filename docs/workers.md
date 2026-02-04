# VidWiz Workers

## Purpose
Explain the background workers and Lambda functions that power async processing: transcript/metadata fetching, AI notes, and AI summaries.

## Scope
- Script helpers (systemd-friendly) for transcript and metadata tasks.
- Lambda functions for AI notes, AI summaries, and task dispatch.
- How workers interact with the internal API, S3, and SQS.

## Components
### Script Helpers (Long-Running)
- **Transcript helper**: `backend/workers/scripts/transcript-helper.py`
  - Polls `/v2/internal/tasks?type=transcript`.
  - Fetches transcripts via `youtube_transcript_api`.
  - Submits results to `/v2/internal/tasks/{id}/result`.
- **Metadata helper**: `backend/workers/scripts/metadata-helper.py`
  - Polls `/v2/internal/tasks?type=metadata`.
  - Fetches metadata via `yt_dlp`.
  - Submits results to `/v2/internal/tasks/{id}/result`.

### Lambda Functions
- **AI Note Lambda**: `backend/workers/lambdas/ai-note.py`
  - Triggered by SQS messages (note payloads).
  - Fetches transcript from S3 and generates a one-line note.
  - Uses Gemini or OpenAI based on `LLM_PROVIDER`.
  - Updates note via internal API.

- **AI Summary Lambda**: `backend/workers/lambdas/ai-summary.py`
  - Triggered by SQS messages (video_id payload).
  - Fetches transcript from S3 and generates a summary.
  - Validates length constraints and updates video summary via internal API.

- **Task Dispatcher Lambda**: `backend/workers/lambdas/tasks-dispatcher.py`
  - Triggered by S3 transcript uploads or manual event input.
  - On S3 event, dispatches:
    - Summary generation to summary SQS.
    - AI note tasks by querying `/v2/internal/videos/{video_id}/ai-notes`.

## Key Flows
### 1) Transcript Fetch
- Backend schedules transcript tasks in DB.
- Transcript helper polls internal API for tasks.
- Transcript is fetched from YouTube and posted to internal API.
- Internal API stores transcript in S3 and marks `transcript_available`.

### 2) Metadata Fetch
- Backend schedules metadata tasks in DB.
- Metadata helper polls internal API for tasks.
- Metadata is fetched via `yt_dlp` and posted to internal API.
- Internal API stores metadata on the `videos` record.

### 3) AI Note Generation
- Backend pushes empty-text notes to SQS when AI notes are enabled and transcript is available.
- AI note Lambda reads transcript from S3, generates a note, and updates the note via internal API.

### 4) AI Summary Generation
- Task dispatcher Lambda is triggered by S3 transcript upload.
- Summary request is sent to summary SQS.
- AI summary Lambda generates a summary and posts to internal API.

## Interfaces / Integration Points
- **Internal API**: `/v2/internal/tasks`, `/v2/internal/videos/*`, `/v2/internal/notes/*`.
- **S3**: transcript storage under `transcripts/{video_id}.json`.
- **SQS**:
  - AI note queue (note payloads).
  - Summary queue (video_id payloads).
- **YouTube APIs/Libraries**: `youtube_transcript_api`, `yt_dlp`.
- **LLMs**: Gemini or OpenAI depending on environment configuration.

## Data / State (High-Level)
- **Task payloads**: contain `video_id` in `task_details`.
- **AI note payloads**: `{ id, video_id, timestamp, user_id }`.
- **AI summary payloads**: `{ video_id }`.
- **Transcript objects**: list of segments with at least `text` and optional `offset`.

## Operational Notes
- Script helpers require `ADMIN_TOKEN` and `API_URL` (default `https://api.vidwiz.online`).
- Lambdas require `VIDWIZ_ENDPOINT` and `VIDWIZ_TOKEN` for internal API access.
- S3 and AWS credentials must be configured for transcript storage and access.
- AI summary and note lambdas enforce length constraints via env config.

## Open Questions
- Do we want to consolidate helper scripts into containerized workers instead of systemd?
- Should dispatcher always enqueue summaries, or only when explicitly requested?

## Interaction Overview (ASCII)
```
DB Tasks
  |
  v
Transcript Helper ----> /v2/internal/tasks (poll)
  |                            |
  +--> YouTube Transcript API  +--> /v2/internal/tasks/{id}/result
                                |
                                v
                               S3 (transcripts)

DB Tasks
  |
  v
Metadata Helper -------> /v2/internal/tasks (poll)
  |                            |
  +--> yt_dlp                  +--> /v2/internal/tasks/{id}/result

S3 transcript upload
  |
  v
Task Dispatcher Lambda
  |\
  | +--> Summary SQS --------> AI Summary Lambda ----> /v2/internal/videos/{id}/summary
  |
  +--> AI Note SQS ----------> AI Note Lambda -------> /v2/internal/notes/{id}
```
