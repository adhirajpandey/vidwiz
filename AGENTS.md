# Repository Guidelines (Agents)

## Purpose
This file is the single source of truth for coding agents working in this repo. It prioritizes accuracy, minimal changes, and alignment with the current codebase.

## Project Overview
VidWiz helps users take timestamped notes on YouTube videos, enriches notes with metadata/transcripts, and supports transcript-grounded AI chat (Wiz). AI notes and summaries are generated asynchronously.

## Rules (Must Follow)
- Start by reviewing relevant docs in `docs/` to understand the current overview.
- Get codebase context (read the files you will touch) and then plan the implementation.
- Keep changes minimal and focused on the request.
- Follow existing code patterns and naming conventions.
- Ensure UI changes are consistent in light and dark mode.
- When making frontend changes, assume the dev server is already running; do not start it again.
- Add tests for backend behavior changes when feasible.
- Do not change app code just to satisfy tests.
- Document notable behavior changes in `README.md` when needed.
- If anything is unclear, ask the user.

## Current Project Structure
- `README.md`: Project overview and setup.
- `AGENTS.md`: This file.
- `.github/workflows/*`: CI/CD workflows.
- `backend/`: FastAPI backend.
  - `src/`: app modules (routers, services, schemas, models, dependencies).
  - `workers/`: background workers and Lambda functions.
  - `infra/`: systemd service unit files for helpers.
  - `wsgi.py`: ASGI entrypoint.
- `frontend/`: Vite + React + TypeScript web app.
  - `src/pages/`: route-level views.
  - `src/components/`: shared UI components.
- `extension/`: Chromium extension assets.
  - `manifest.json`, `popup.*`, `icons/`.
- `docs/`: living documentation set.

## Build, Test, and Development Commands
### Backend
- Install: `cd backend && poetry install`
- Run (local): `cd backend && poetry run uvicorn src.main:app --host 0.0.0.0 --port 5000`
- Tests: `cd backend && poetry run pytest`

### Frontend
- Install: `cd frontend && npm install`
- Run: `cd frontend && npm run dev`

## Architecture
- Refer to `docs/architecture.md` for system-level interactions.
- Refer to `docs/backend.md`, `docs/frontend.md`, `docs/workers.md`, and `docs/extension.md` for subsystem details.

## Auth and Access Rules (Important)
- **JWT tokens**: required for most `/v2` endpoints.
- **Long-term tokens**: accepted only for note creation (extension/mobile).
- **Guest sessions**: `X-Guest-Session-ID` header is used for Wiz chat without JWT.
- **Admin token**: required for `/v2/internal` endpoints.

## Documentation Rules
- Prefer `docs/*` for new or updated documentation.
- Keep docs accurate to the current codebase; remove outdated claims.
- Use ASCII-only diagrams in docs unless explicitly asked otherwise.

## When in Doubt
- Ask before making assumptions about product behavior.
- If a change touches multiple subsystems, summarize impact in `docs/` or `README.md`.
