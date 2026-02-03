# Async Tasks (End-to-End Flow)

This document describes where asynchronous work is scheduled and how it flows through VidWiz.

## 1) Video first seen -> schedule metadata + transcript

When a conversation is created, the backend ensures a video exists and schedules two internal tasks:

- `backend/src/conversations/service.py` -> `get_or_create_video()`
  - Creates the `Video` row if missing.
  - Calls `internal_service.create_task_idempotent(...)` for:
    - `FETCH_METADATA_TASK_TYPE`
    - `FETCH_TRANSCRIPT_TASK_TYPE`

These tasks are stored in the `tasks` table (`backend/src/internal/models.py`) and exposed via internal endpoints in `backend/src/internal/router.py`.

## 2) Internal worker loop -> fetch metadata/transcript

Two helper workers poll and execute internal tasks:

- `backend/workers/scripts/metadata-helper.py`
- `backend/workers/scripts/transcript-helper.py`

Flow:

1. Poll `GET /api/v2/internal/tasks?type=metadata|transcript`.
2. Fetch YouTube metadata/transcript.
3. Submit results via `POST /api/v2/internal/tasks/{task_id}/result`.

Result handling (`backend/src/internal/service.py`):

- Metadata saved to `Video.video_metadata`.
- Transcript saved to S3 at `transcripts/{video_id}.json`.
- `video.transcript_available` set to `true`.

## 3) Transcript stored in S3 -> dispatch downstream work

An S3 "object created" event triggers `backend/workers/lambdas/tasks-dispatcher.py`.

The dispatcher:

- Enqueues a summary request to the summary SQS queue (via `push_summary_to_sqs()`), and
- Fetches pending AI-note tasks for the video and sends them to the AI-note SQS queue in batches of 10 (via `fetch_all_notes()` + `push_notes_to_sqs_batch()`).

## 4) Summary generation

Summary requests are processed by `backend/workers/lambdas/ai-summary.py`:

1. Fetch transcript from S3.
2. Fetch metadata (title) from VidWiz API if needed.
3. Generate summary via LLM.
4. Persist summary back to VidWiz via `POST /v2/internal/videos/{video_id}/summary`.

## 5) AI note generation

AI note generation has two entry points:

- **Immediate enqueue on note creation**
  - `backend/src/notes/service.py` -> `create_note_for_user()`
  - Conditions:
    - Note text is empty
    - User has `ai_notes_enabled`
    - Transcript is already available
  - Enqueues a single note to SQS via `push_note_to_sqs()`.

- **Batch enqueue after transcript arrives**
  - `backend/workers/lambdas/tasks-dispatcher.py` fetches pending notes for the video and enqueues them in batches.

The AI-note worker `backend/workers/lambdas/ai-note.py`:

1. Reads note payloads from SQS.
2. Fetches transcript from S3.
3. Extracts relevant transcript context at the note timestamp.
4. Generates note text via LLM.
5. Updates the note via VidWiz API (PATCH with `generated_by_ai=true`).
