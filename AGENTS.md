# Repository Guidelines

## Project Overview
VidWiz helps users take timestamped notes on YouTube videos. The system stores notes, enriches them with video metadata, and can generate AI summaries for specific timestamps when configured.

## Rules
- Plan changes thoughtfully before actual implementation.
- Keep changes minimal and focused on the request.
- In case of any doubts, ask the user for clarification.
- Add tests for backend behavior changes when feasible.
- Document notable behavioral changes in the README when needed.

## Project Structure & Module Organization
- `backend/`: Flask API and supporting files.
  - `vidwiz/`: Flask app package.
    - `routes/`: API route handlers.
    - `shared/`: Shared helpers/utilities.
    - `tests/`: Pytest suites.
  - `.env`: Local environment variables (use `.env.example`).
  - `wsgi.py`: Flask entrypoint for dev server.
- `frontend/`: Vite + React + TypeScript UI.
  - `src/`: React application source.
    - `pages/`: Route-level views.
    - `components/`: Shared UI components.
  - `index.html`: Vite HTML template.
  - `vite.config.*`: Vite build configuration.
- `extension/`: Chromium extension assets.
  - `manifest.json`: Extension manifest.
  - `popup.*`: Popup UI assets/scripts.
  - `icons/`: Extension icons.
- Root: Docker Compose files for local/prod orchestration.
  - `docker-compose.yml`: Local dev orchestration.
  - `docker-compose.prod.yml`: Production orchestration.
  - `README.md`: Project overview and setup.

## Build, Test, and Development Commands
- `cd backend && poetry install`: Install backend dependencies.
- `cd backend && python wsgi.py`: Run Flask dev server.
- `cd backend && poetry run pytest`: Run backend tests (pytest).
- `cd frontend && npm install`: Install frontend dependencies.
- `cd frontend && npm run dev`: Start Vite dev server

## Architecture Overview
- Extension -> Flask API -> PostgreSQL
- Web app (Vite/React) -> Flask API -> PostgreSQL
- Flask API -> AWS SQS (async tasks) -> AWS S3 (artifacts/outputs)

## General Flows
- User creation: Web app or extension -> `POST /api/users` -> store user in PostgreSQL -> return JWT for subsequent requests.
- Video creation: Web app or extension -> `POST /api/videos` -> fetch metadata/transcript helpers -> store video + metadata -> return video record.
- Note creation: Web app or extension -> `POST /api/notes` -> store note + timestamp -> optional async AI note via SQS -> update note with generated content.

## Configuration & Secrets
- Backend environment variables live in `backend/.env`; use `backend/.env.example` as the template.
- Extension endpoints are configured in `extension/popup.js` (`AppURL`, `ApiURL`).
