# VidWiz

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/brand/vidwiz-wordmark-on-dark.svg">
  <img src="frontend/public/brand/vidwiz-wordmark-on-light.svg" alt="VidWiz" width="280">
</picture>

Brand assets and regeneration instructions are in [docs/branding.md](docs/branding.md).

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

## Quick start
Prerequisites: Python 3.13, uv 0.8.22, Node.js, pnpm, and PostgreSQL. VidWiz
runs on PostgreSQL only; its migrations and search use PostgreSQL features.
Production deployment configuration is kept outside this repository.

### Database
Run a local PostgreSQL that matches the template's `DB_URL`, for example:

```sh
docker run -d --name vidwiz-db -p 5432:5432 \
  -e POSTGRES_USER=vidwiz -e POSTGRES_PASSWORD=change-me -e POSTGRES_DB=vidwiz \
  pgvector/pgvector:pg17
```

### Backend
1. `cd backend`
2. Install dependencies: `uv sync --locked`
3. Copy the root environment template: `cp ../.env.example .env`.
4. Fill the required values listed in `docs/backend.md`. The API starts with
   placeholder AWS and payment values, but features that use them fail.
5. Apply migrations: `uv run --locked alembic upgrade head`
6. Start server: `uv run --locked uvicorn src.main:app --host 0.0.0.0 --port 5000`
7. Open Swagger UI at `http://localhost:5000/docs` or fetch the generated
   OpenAPI schema from `http://localhost:5000/openapi.json`.

Transcripts, metadata, and title resolution come from helpers that poll the
API. Run the ones you need from `backend/`, each in its own terminal:

```sh
uv run --locked --env-file .env python workers/scripts/task-helper.py transcript
uv run --locked --env-file .env python workers/scripts/task-helper.py metadata
uv run --locked --env-file .env python workers/scripts/task-helper.py resolve_title
uv run --locked --env-file .env python -m src.management.sweep --every 600
```

AI lines and overviews run on AWS Lambda through SQS (see
`docs/aws-infrastructure.md`). Without real queues they stay queued until the
sweep marks them failed.

Every client captures moments through `POST /v2/captures`, with a video URL or
ID, or a title when the client cannot see the ID. See `docs/backend.md`.

### Frontend
1. `cd frontend`
2. Install dependencies: `pnpm install --frozen-lockfile`
3. Start development server: `pnpm dev`

## Extension setup
1. Build for your local web app and API:
   `node extension/build.mjs --web http://localhost:5173 --api http://localhost:5000/v2 --out extension/dist/dev`
2. In a Chromium browser, open `chrome://extensions`, turn on Developer mode,
   and load `extension/dist/dev` with **Load unpacked**.
3. Start the web app with `VITE_EXTENSION_ID` set to the unpacked extension's
   ID, so login sync reaches it.
4. Log in to the web app. The extension picks up the login and works on
   YouTube videos and Shorts.

See `docs/extension.md` for production builds and the Chrome Web Store zip.

## Running tests
- Backend: `cd backend && uv sync --locked && uv run --locked ruff format --check src workers && uv run --locked ruff check src workers && TEST_DB_URL=postgresql://user:password@localhost:5432/vidwiz_test uv run --locked pytest`
  - Tests need a disposable PostgreSQL database with pgvector, such as the
    `pgvector/pgvector:pg17` image. Each run drops and recreates its `public`
    schema, so never point `TEST_DB_URL` at a database you want to keep.
- Extension builder: `node --test extension/output.test.mjs`
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

### Video overview

![A video overview with timestamped key points](docs/images/video-overview.png)

### Library

![Saved videos with their moments and transcript status](docs/images/library.png)

### Ask your library

![An answer with citations to saved videos](docs/images/ask-answer.png)

### Home after a capture

![Recent captures with AI lines on the home page](docs/images/home.png)

### Extension
<img width="369" height="450" alt="Screenshot 2026-01-16 011711" src="https://github.com/user-attachments/assets/d52c10c5-fcaa-4d0b-8dae-e2f63b7c2f66" />
