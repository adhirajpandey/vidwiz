# VidWiz

## Description
VidWiz transforms how you learn from YouTube videos by combining two powerful AI-driven features:

**Smart Notes** - Stop pausing to type. VidWiz automatically extracts insights and creates timestamp-linked notes, building your personal knowledge vault. AI captures the core concepts while you stay focused on learning.

**Wiz** - Ask questions instead of scrubbing through timelines. This conversational AI assistant answers based on the video transcript, providing context-aware responses with precise jump-links to relevant moments.

The platform is built with:
- **Frontend**: React (Vite) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python) REST API
- **Database**: PostgreSQL for data persistence
- **AI/LLM**: OpenAI/Gemini models for intelligent note generation and wiz chat
- **Cloud**: AWS (SQS for async processing, S3 for storage)

[Check Screenshots](#screenshots)

## Features

### Two Powerful Learning Tools

**1. Smart Notes - Automatic Knowledge Capture**
   - **Auto-Extraction**: AI automatically captures core insights from any timestamp
   - **Precision Timestamps**: Click any note to jump directly to that moment in the video
   - **Rich Metadata**: Thumbnails, channel info, view counts, and duration tracking

**2. Wiz - Conversational Video Intelligence**
   - **Ask in plain English**: Ask questions in plain English, get expert answers
   - **Context-Aware**: Wiz understands the video content and watches alongside you
   - **Deep Jump-Links**: Click on answers to play the exact video moment

### Multi-Platform Access
   - **Browser Extension**: Works with any Chromium-based browser (Chrome, Edge, Brave, etc.)
   - **Web Dashboard**: Modern UI for managing notes and videos
   - **Android**: Integration via Macrodroid macros
   - **iOS**: Integration via Shortcuts automation

### Privacy & Control
   - **Self-Hosted Deployments**: Run VidWiz on your infrastructure and control where data lives.
   - **Pluggable AI**: Choose Gemini or OpenAI via environment configuration.
   - **Token-Based Access**: Use long-term tokens for extensions and mobile automations.

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
      │           ├─ Task queue (DB) -> Helpers (transcript/metadata)
      │           ├─ SQS (Async task queues) -> Lambdas (AI notes/summary)
      │           └─ S3 (Transcripts)
```

Quick start
Prereqs: Python 3.10–3.13, Node.js, Poetry, running PostgreSQL

### Backend
1. `cd backend`
2. Install dependencies: `poetry install`
3. Configure `.env` (use `.env.example` as reference). For required environment variables, see `docs/backend.md`.
4. Start server: `poetry run uvicorn src.main:app --host 0.0.0.0 --port 5000`

### Frontend
1. `cd frontend`
2. Install dependencies: `npm install`
3. Start development server: `npm run dev`

## Extension setup
1) Load unpacked from `extension/` in a Chromium browser (`chrome://extensions` → Developer mode → Load unpacked)
2) Configure `AppURL` and `ApiURL` in `extension/popup.js` to match your deployment
3) Open the extension popup - you'll see a token setup screen
4) Get your API token:
   - Log in to the web dashboard
   - Go to **Profile** → **Developer Access**
   - Click **Generate New** to create a long-term token
   - Copy the token
5) Paste the token in the extension popup and click **Save Token**

The extension will then show the note-taking interface when on YouTube videos.

## Running tests
- Backend: `cd backend && poetry run pytest`

## Project Structure
```
vidwiz/
├── backend/              # FastAPI backend
│   ├── src/              # App modules (routers, services, schemas, models)
│   ├── workers/          # Background workers and lambdas
│   ├── infra/            # Systemd/service unit files for helpers
│   └── wsgi.py           # ASGI entrypoint
├── frontend/            # React + Vite web app
│   └── src/
│       ├── pages/       # Route-level views
│       ├── components/  # Reusable UI components
│       └── public/      # Static assets
└── extension/           # Chromium browser extension
    ├── manifest.json
    ├── popup.*
    └── icons/
```

## Roadmap
- [x] Smart Notes feature with AI auto-extraction
- [x] Wiz conversational AI assistant
- [x] Lambda workflow optimization
- [x] SQS async task processing
- [x] Glassmorphic UI/UX redesign
- [x] Multi-platform support (Extension, Web, iOS, Android)
- [x] Move backend from Flask to FastAPI
- [x] Proper CI/CD workflows for backend and frontend
- [x] Cloud-hosted SaaS offering with credits model
- [ ] Semantic search across notes and videos
- [ ] Universal export (Markdown, PDF)
- [ ] Bring-your-own AI key(BYOK) support



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
