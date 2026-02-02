# Wiz Integration Review Findings (Jan 24, 2026)

This document records issues found in the Wiz integration and suggested fixes. It is intended to preserve enough context so each fix can be applied later without re-investigation.

## 1) New Chat does not create a new backend conversation
**Severity:** High

**What happens now**
- The UI "New" button only clears local messages.
- Backend `get_or_create_conversation` always reuses the same conversation for a user/guest + video.
- Result: "New" chat still uses prior history in the LLM prompt, which is a privacy/UX mismatch.

**Evidence**
- Frontend new chat only resets local state: `frontend/src/pages/WizWorkspacePage.tsx:449`
- Backend always reuses conversation: `backend/vidwiz/routes/wiz_routes.py:231`, `backend/vidwiz/routes/wiz_routes.py:398`

**Spec mismatch**
- PRD/TRD says "Always start a new conversation thread per entry."

**Potential fix**
- Decide on the intended behavior:
  - If "New" should start a fresh server thread, add a new conversation identifier in requests (e.g., `conversation_id` or `session_id`) and have backend create a new Conversation when it changes.
  - Alternatively, add a `/wiz/conversation` endpoint to explicitly create a new conversation and return an ID, then include it in chat requests.
- Update the frontend to call the conversation creation endpoint on entry and on "New", and pass the conversation ID in `/wiz/chat`.
- Update backend to respect the conversation ID and not auto-reuse old threads.
- Add tests for: (1) new conversation created on new entry, (2) “New” uses a new conversation and excludes previous messages from the prompt history.

## 2) Transcript/metadata tasks can get stuck in a non-requeueable state
**Severity:** High

**What happens now**
- `has_active_task` treats `COMPLETED` as active.
- `/wiz/init` skips creating a new task if a completed task exists, even if the transcript or metadata is missing.
- If a task completed but produced no data (or data is lost), the video is stuck.

**Evidence**
- `has_active_task` includes `COMPLETED`: `backend/vidwiz/routes/wiz_routes.py:94`
- `/wiz/init` checks only `transcript_available`/`video_metadata` plus `has_active_task`: `backend/vidwiz/routes/wiz_routes.py:149`

**Potential fix**
- Change `has_active_task` to only consider `PENDING` and `IN_PROGRESS` for gating new tasks.
- Optional: add a freshness or "result exists" check (e.g., requeue if `transcript_available` is false regardless of completed tasks).
- Add a defensive requeue in `get_valid_transcript_or_raise` if `transcript_available` is true but S3 data is missing (see finding #5).
- Add tests: (1) completed task with missing transcript should requeue, (2) pending/in-progress should still block requeue.

## 3) Backend video_id validation is too permissive
**Severity:** Medium

**What happens now**
- Backend accepts any non-empty `video_id`, so invalid IDs or playlist URLs can be stored and queued.
- Frontend already rejects playlist URLs and enforces 11-char IDs.

**Evidence**
- Validation only checks non-empty: `backend/vidwiz/shared/schemas.py:257`, `backend/vidwiz/shared/schemas.py:356`

**Spec mismatch**
- TRD requires validation on both frontend and backend; playlist URLs should be rejected server-side.

**Potential fix**
- Add strict validation in backend:
  - Accept only 11-char YouTube IDs (`^[a-zA-Z0-9_-]{11}$`), or
  - Accept full URLs and parse server-side (mirror `extractVideoId` behavior).
- Return a validation error with a stable error code for invalid IDs.
- Add tests for invalid playlist URLs and malformed IDs.

## 4) Rate limiting (per-minute + per-IP) not implemented
**Severity:** Medium

**What happens now**
- Only daily quotas are enforced (user/guest).
- No per-minute throttling or per-IP limits.

**Evidence**
- No limiter usage or per-IP checks; only `check_daily_quota`: `backend/vidwiz/routes/wiz_routes.py:53`

**Spec mismatch**
- TRD requires 10 req/min and per-IP safety net.

**Potential fix**
- Add a rate limiter (e.g., Flask-Limiter) with:
  - 10 req/min per user (authenticated) + IP
  - 10 req/min per guest session + IP
  - A fallback per-IP limit for unauthenticated traffic
- Return consistent 429 error payloads including a reason code.
- Add tests verifying 429 response for burst traffic and that daily quota still applies.

## 5) Transcript “available” but missing in S3 leads to hard failure
**Severity:** Medium

**What happens now**
- If `transcript_available` is true but S3 does not return data, the chat returns 404 ("Transcript data missing") and does not requeue.

**Evidence**
- `get_valid_transcript_or_raise` throws 404 on missing S3 transcript: `backend/vidwiz/routes/wiz_routes.py:224`

**Potential fix**
- If `transcript_available` is true but S3 returns no data:
  - Queue a transcript task again and return 202 `processing`, or
  - Mark `transcript_available` false and trigger a re-fetch.
- Add a test that simulates missing S3 transcript with `transcript_available` true and verifies a requeue/202.

## 6) Polling timeout and UX mismatch with spec
**Severity:** Low

**What happens now**
- UI polls up to 60 seconds and then shows a “refresh page” modal.

**Evidence**
- Timeout is 60s: `frontend/src/pages/WizWorkspacePage.tsx:229`

**Spec mismatch**
- TRD says prompt retry after 30s.

**Potential fix**
- Reduce polling timeout to 30s and update modal copy to “Retry” instead of “Refresh page.”
- Optional: preserve the current 60s if product decision changed; document it in spec/README if so.

## 7) Missing GEMINI_API_KEY handled inside streaming path
**Severity:** Low

**What happens now**
- The SSE stream yields an error chunk when the key is missing.
- This is late and harder to handle on the client.

**Evidence**
- `stream_wiz_response` checks key and yields error chunk: `backend/vidwiz/routes/wiz_routes.py:289`

**Potential fix**
- Preflight in `chat_wiz` before creating a streaming response:
  - If key missing, return a standard 500 JSON error.
- Add a test for missing key to ensure non-streaming error response.

## 8) RateLimitError “details” shape mismatch with shared error schema
**Severity:** Low

**What happens now**
- `RateLimitError` expects `details` to be a list, but `check_daily_quota` passes a dict.
- Frontend currently expects `error.details.reset_in_seconds`, so it works, but it’s inconsistent with the shared error contract.

**Evidence**
- `RateLimitError` details uses list: `backend/vidwiz/shared/errors.py:118`
- Daily quota passes dict: `backend/vidwiz/routes/wiz_routes.py:87`

**Potential fix**
- Align schema by either:
  - Allowing `details` to be a dict in `APIError`, or
  - Wrapping details in a list with a known shape (and update frontend accordingly).
- Add a test ensuring 429 payload shape is stable.

