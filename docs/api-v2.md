# VidWiz API v2

## What
This document defines the v2 REST surface for VidWiz (timestamped notes, video enrichment, and AI chat).

## Why
We are doing a v2 cut to standardize naming, tighten auth rules, and make async video readiness easier to consume.

## Changes
- Resource-first paths under `/api/v2` with consistent nouns.
- Implicit video creation (no explicit create endpoint).
- Conversations modeled as `/conversations/{id}/messages`.
- Video SSE stream that emits snapshot/update/done.
- Internal worker write-backs isolated under `/internal`.

Legend: **Auth** = Public | User JWT | User JWT or Long-term | Guest | User JWT or Guest | Admin token

## Auth & Users
- `POST /api/v2/auth/register` — Create a user account. **Auth:** Public
- `POST /api/v2/auth/login` — Authenticate and return JWT. **Auth:** Public
- `POST /api/v2/auth/google` — Google ID token login. **Auth:** Public
- `POST /api/v2/auth/tokens` — Create long-term token. **Auth:** User JWT
- `DELETE /api/v2/auth/tokens` — Revoke long-term token. **Auth:** User JWT
- `GET /api/v2/users/me` — Fetch current profile. **Auth:** User JWT
- `PATCH /api/v2/users/me` — Update profile fields. **Auth:** User JWT

## Videos
- `GET /api/v2/videos/{video_id}` — Fetch current video state (metadata, transcript_available, summary). **Auth:** User JWT
- `GET /api/v2/videos` — Search/filter videos (q, pagination, sort). **Auth:** User JWT
- `GET /api/v2/videos/{video_id}/stream` — SSE stream of video state; emits snapshot/update/done when **metadata + transcript + summary** are all ready (timeout 60s). **Auth:** User JWT or Guest

Notes:
- `GET /api/v2/videos/{video_id}` returns a video for any authenticated user (no note ownership requirement).

## Notes (Endpoints)
- `GET /api/v2/videos/{video_id}/notes` — List notes for a video. **Auth:** User JWT
- `POST /api/v2/videos/{video_id}/notes` — Create a note; implicitly creates video if missing. **Auth:** User JWT or Long-term
- `PATCH /api/v2/notes/{note_id}` — Update note text/flags. **Auth:** User JWT
- `DELETE /api/v2/notes/{note_id}` — Delete a note. **Auth:** User JWT

## Conversations / Wiz
- `POST /api/v2/conversations` — Start conversation for a video; implicit video create. **Auth:** User JWT or Guest
- `GET /api/v2/conversations/{conversation_id}` — Conversation metadata. **Auth:** User JWT or Guest (owner)
- `GET /api/v2/conversations/{conversation_id}/messages` — List messages. **Auth:** User JWT or Guest (owner)
- `POST /api/v2/conversations/{conversation_id}/messages` — Send message + SSE stream. **Auth:** User JWT or Guest

## Internal / Worker
- `GET /api/v2/internal/tasks?type=transcript&timeout=` — Poll for work items. **Auth:** Admin token
- `POST /api/v2/internal/tasks/{task_id}/result` — Submit task result. **Auth:** Admin token
- `GET /api/v2/internal/videos/{video_id}/ai-notes` — Fetch eligible notes for AI note generation. **Auth:** Admin token
- `POST /api/v2/internal/videos/{video_id}/transcript` — Store transcript data (upsert video). **Auth:** Admin token
- `POST /api/v2/internal/videos/{video_id}/metadata` — Store metadata data (upsert video). **Auth:** Admin token
- `POST /api/v2/internal/videos/{video_id}/summary` — Store summary text (upsert video). **Auth:** Admin token

## Notes
- Global error payload is standardized across routes:
  - `{"error": {"code": "...", "message": "...", "details": [...]}}`

## Open Questions
- Should implicit video creation (notes create) enqueue transcript/metadata tasks in v2?
- Is `video_title` required when a note implicitly creates a video?
- Should conversation creation return a legacy `conversation_id` field for client compatibility?
- Should `POST /api/v2/conversations/{conversation_id}/messages` return `202` with a processing payload when transcripts are still pending?
- Should `GET /api/v2/internal/tasks` return a JSON timeout payload instead of `204 No Content`?
- Should internal endpoints accept full YouTube URLs (in addition to raw 11-char IDs) for `video_id`?
- Should the admin token be scoped separately for internal worker traffic?
