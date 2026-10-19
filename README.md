# VidWiz

## Description
VidWiz helps you keep what you learn from YouTube. Tap while watching, and
VidWiz saves the moment: the exact words from the transcript, an optional AI
line, and your note. Later, search everything you saved and everything said in
your saved videos, or ask a question across your whole library and get an answer
with citations that play the source.

- **Capture**: one tap on a phone automation, Alt+S in the browser extension,
  or one button in the web player. Captures close together merge, and
  title-only captures from a phone resolve to the right video in the background.
- **Revisit**: ranked full-text search over moments and transcripts, with
  typo tolerance, highlighted excerpts, and links that open the video at the
  second it was said. Each video has an overview with timestamped key points.
- **Ask**: ask about one video or the whole library. Answers are grounded in
  transcripts and moments, and every citation can be played or saved as a
  moment.

The platform is built with:
- **Frontend**: React (Vite), TypeScript, Tailwind CSS, TanStack Query
- **Backend**: FastAPI with SQLAlchemy and Alembic
- **Database**: PostgreSQL, including full-text search
- **Workers**: long-running helpers for transcripts, metadata, and title
  resolution; AWS Lambda for AI moments and overviews
- **Cloud**: AWS S3, SQS with dead-letter queues, and Lambda, defined with CDK
- **AI**: OpenRouter, with a separate model for each workload, and the Jev
  decision model for relevance scoring

## Architecture

VidWiz uses a layered backend to keep request handling thin and domain logic centralized, with workers and Lambdas for async processing:

```
Clients (Extension/Web/Mobile)
    ↓
FastAPI REST API (routers/controllers)
    ↓
Service layer (domain logic)
    ↓
PostgreSQL ←→ Workers + AWS Services
      │           ├─ Task queue (DB) -> Helpers (transcript/metadata/title)
      │           ├─ SQS (+ dead-letter queues) -> Lambdas (AI moments/overviews)
      │           └─ S3 (Transcripts) -> dispatcher Lambda
```

Quick start
Prereqs: Python 3.13, uv 0.8.22, Node.js, running PostgreSQL

### Backend
1. `cd backend`
2. Install dependencies: `uv sync --locked`
3. Copy the root environment template: `cp ../.env.example .env`.
4. When running the API outside Compose against the Compose PostgreSQL container, change the `DB_URL` host and port from `database:5432` to `localhost:5433`.
5. Fill the required values documented in `docs/backend.md`.
6. Apply migrations: `uv run --locked alembic upgrade head`
7. Start server: `uv run --locked uvicorn src.main:app --host 0.0.0.0 --port 5000`
8. Open Swagger UI at `http://localhost:5000/docs` or fetch the generated
   OpenAPI schema from `http://localhost:5000/openapi.json`.

Every client captures moments through `POST /v2/captures`, with a video URL or
ID, or a title when the client cannot see the ID. See `docs/backend.md`.

### Frontend
1. `cd frontend`
2. Install dependencies: `pnpm install --frozen-lockfile`
3. Start development server: `pnpm dev`

## Extension setup
1) Load unpacked from `extension/` in a Chromium browser (`chrome://extensions` → Developer mode → Load unpacked)
2) Configure deployment URLs in `extension/popup.js`:
   - `CONSTANTS.API.BASE_URL`
   - `CONSTANTS.API.API_URL`
3) Configure your web origin for web-to-extension auth sync:
   - `extension/manifest.json` → `externally_connectable.matches`
   - `extension/background.js` → `CONSTANTS.ORIGINS.PROD`
4) Set the extension ID used by the web app:
   - `frontend/src/config.ts` → `EXTENSION_ID` (production must be a real ID, not placeholder)
5) Reload both extension and web app, then log in (or just open the web app if already logged in)
6) Open the extension popup; it auto-unlocks when token sync succeeds

The extension note UI appears on supported YouTube watch pages after sync.

## Running tests
- Backend: `cd backend && uv sync --locked && uv run --locked ruff format --check src workers && uv run --locked ruff check src workers && TEST_DB_URL=postgresql://user:password@localhost:5432/vidwiz_test uv run --locked pytest`
  - Tests need a disposable PostgreSQL database with pgvector, such as the
    `pgvector/pgvector:pg17` image. Each run wipes and migrates it.
- Frontend: `cd frontend && pnpm install --frozen-lockfile && pnpm lint && pnpm test && pnpm build`
- AWS infrastructure: `cd infra && uv sync --locked && npm ci --ignore-scripts && uv run --locked python scripts/validate.py`

GitHub Actions runs these three checks in parallel for every pull request to
`main` and every push to `main`. On `main`, the backend container image is
published only when the push changes the image's backend files, and only after
the backend checks pass. Each image is tagged `latest` and `sha-<commit>`, so an
earlier image stays available for rollback. When a push to `main` changes
`frontend/` or `wrangler.jsonc`, the frontend build from the checks is deployed
to Cloudflare Workers.

Production AWS serverless resources are defined in `infra/` as
`vidwiz-v3-stack`. See `docs/aws-infrastructure.md` before any bootstrap,
deployment, transcript migration, or cutover operation.

## Project Structure
```
vidwiz/
├── backend/              # FastAPI backend
│   ├── src/              # Domains: auth, moments, library, search, conversations, ...
│   ├── migrations/       # Alembic migrations
│   └── workers/          # Background helpers and Lambdas
├── frontend/             # React + Vite web app
│   └── src/
│       ├── app/          # Shell, command palette, query client
│       ├── features/     # Pages by area: home, video, search, ask, settings, ...
│       ├── components/   # UI primitives and the chat thread
│       └── api/          # API client and types
├── infra/                # AWS CDK app and assertions
└── extension/            # Chromium extension (MV3, plain JavaScript)
```

## Roadmap
- [x] Timestamped capture from the extension, web, and phone automations
- [x] Transcript-grounded chat with server-resolved citations
- [x] Async AI work on SQS and Lambda, with dead-letter queues
- [x] Credits and payments
- [x] Moments with quotes, explicit AI states, and merge of nearby captures
- [x] Full-text search across moments and transcripts
- [x] Library-wide questions with cited sources
- [x] Overviews with timestamped key points
- [x] Markdown export
- [ ] Embedding-based search, if full-text search misses too often
- [ ] Bring-your-own AI key (BYOK) support

## Demo

<video src="https://github.com/user-attachments/assets/cf4a872f-b683-4566-9115-abf470ba8f54" controls></video>


## Screenshots

### Smart Notes Feature
![Smart Notes](frontend/src/public/smart-notes.png)
*Rich note-taking with timestamp navigation and video metadata*

### Ask Wiz - AI Assistant
![Ask Wiz](frontend/src/public/wiz.png)
*AI-powered note generation and intelligent assistance for your learning journey*

### Extension
<img width="369" height="450" alt="Screenshot 2026-01-16 011711" src="https://github.com/user-attachments/assets/d52c10c5-fcaa-4d0b-8dae-e2f63b7c2f66" />
