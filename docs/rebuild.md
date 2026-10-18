# VidWiz v3 Rebuild

## Purpose
Record the agreed plan for the v3 rebuild: what changes, what stays, and the
order of work. Remove this file once v3 is live and the subsystem docs describe
the new behavior.

## Product
Tap while watching. VidWiz remembers what was said and finds it again.

The core unit is a **moment**: a video, a time range, the transcript lines
around it (the quote), an optional AI line, and an optional note written by the
user. The product has three verbs:

- **Capture**: one tap on a phone, one shortcut in the extension, or one button
  in the web player.
- **Revisit**: search saved moments and transcripts by keyword or meaning, then
  jump to the source.
- **Ask**: ask about one video or across the whole library, with timestamp
  citations resolved by the server.

## What stays
- Architecture: FastAPI, PostgreSQL, the transcript and metadata helpers, S3,
  SQS, the Lambda workers, and the CDK stack.
- Monetization: credits, prices, and Dodo Payments. AI moments cost 1 credit.
  Unlocking Ask for a video costs 5 credits.
- Auth: Google sign-in, email and password (required for extension store
  review), and personal API tokens.
- Transcript fetching. There is no transcript fallback.

## What changes

### Data model
- `notes` becomes `moments` with `start_seconds`, `end_seconds`, `quote`,
  `ai_text`, `note`, `source`, and an explicit `status`:
  `resolving`, `waiting_transcript`, `generating`, `ready`, `no_transcript`,
  or `failed`.
- AI generation is requested explicitly per capture. The user preference only
  sets the client default. Empty text no longer implies AI.
- `library_items` records explicitly saved videos. Videos used only in chat
  appear in the library.
- `api_tokens` stores named, hashed, revocable personal tokens with a last-used
  time. Existing long-term tokens are hashed in place.
- `conversations.scope` is `video` or `library`; `video_id` is nullable for
  library chats.
- `transcript_chunks` and `moments.embedding` use pgvector.
- Schema changes go through Alembic, starting from a baseline that matches the
  current production schema.

### Backend
- `POST /v2/captures` replaces `POST /v2/videos/{id}/notes` and
  `POST /v2/notes/by-title`. It accepts a video URL or ID, or a title and
  channel, plus the time, an optional note, the AI flag, and the client source.
- Title-only captures return immediately as `resolving`. The metadata helper
  resolves them with `yt-dlp` search, checking the user's recent videos first.
  `YOUTUBE_DATA_API_KEY` is no longer needed.
- A capture within 10 seconds of the user's existing moment on the same video
  merges into it. Merged captures are not charged again.
- `GET /v2/search` combines PostgreSQL full-text ranking with vector similarity
  across moments and transcript passages.
- Library Ask retrieves moments and passages across the user's library and
  reuses the structured citation stream. It is free within the existing daily
  message quota.
- Conversations can be listed and resumed.
- A cited passage can be saved as a moment without AI or credits.
- `GET /v2/videos/{id}/transcript` and Markdown export for a video or the whole
  library.
- Removed: `/v2/notes/by-title`, `/v2/videos/library-summary`, and the
  empty-text AI rule.

### Workers
- The AI note worker becomes the moment worker. It returns `ai_text`, `quote`,
  and `end_seconds` from the transcript window it already reads, and skips
  moments that are already `ready`.
- The summary worker returns an overview: a summary plus key points cited to
  transcript chunks, resolved to timestamps by the API. Starter questions stay.
- A new embedding worker embeds transcript windows and moments.
- The dispatcher also enqueues transcript embedding on upload.

### Frontend
A new app on the same stack (Vite, React, TypeScript, Tailwind) with TanStack
Query and Radix primitives. Existing API, SSE, auth, player, chat, and citation
code is reused.

- Home: search, Ask your library, recent moments grouped by video.
- Video workspace `/v/:id`: player with Moments, Ask, Transcript, and Overview
  tabs. Deep links with `?t=`, `?m=`, and `?c=`.
- Search, library Ask with history, Library, Settings, auth, and landing pages.
- Installable PWA with an Android share target, and a command palette.
- Quiet visual design: one accent, flat surfaces, identical light and dark
  themes, mobile first, and costs shown on paid actions.

### Extension
- `Alt+S` captures the current moment and shows an in-page toast.
- The popup lists the current video's moments with seek links.
- Shorts and `youtu.be` URLs are supported.
- A build script sets API and web origins for development builds.
- Auth stays as web login sync.

## Rollout
v3 runs as a second, complete deployment beside the current one:

1. A separate CDK stack with its own bucket, queues, and workers.
2. A separate API, database, and helpers, restored from a production dump and
   migrated.
3. Testing on the v3 deployment with a dedicated email and password account.
4. Cutover: re-sync the latest production data, move the public API and
   frontend to v3, then delete the old stack.

## Phases
0. v3 deployment running the current code against restored data.
1. Alembic baseline, moments, library items, API tokens, captures, title
   resolution, and the moment worker.
2. Embeddings, search, Ask scopes, conversation history, transcript endpoint,
   and overviews.
3. New frontend.
4. Extension.
5. Cutover.

## Out of scope
Pricing changes, transcript fallback, folders and tags, teams, native apps, and
sources other than YouTube.
