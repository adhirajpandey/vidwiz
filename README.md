# VidWiz

## Description
VidWiz transforms how you learn from YouTube videos by combining two powerful AI-driven features:

**Smart Notes** - Stop pausing to type. VidWiz automatically extracts insights and creates timestamp-linked notes, building your personal knowledge vault. AI captures the core concepts while you stay focused on learning.

**Wiz** - Ask questions instead of scrubbing through timelines. This conversational AI assistant understands video content semantically, providing context-aware answers with precise jump-links to relevant moments across your entire video library.

The platform is built with:
- **Frontend**: React (Vite) with TypeScript and Tailwind CSS
- **Backend**: Flask (Python) REST API
- **Database**: PostgreSQL for data persistence
- **AI/LLM**: OpenAI/Gemini models for intelligent note generation and semantic search
- **Cloud**: AWS (SQS for async processing, S3 for storage)

[Check Screenshots](#screenshots)

## Features

### Two Powerful Learning Tools

**1. Smart Notes - Automatic Knowledge Capture**
   - **Auto-Extraction**: AI automatically captures core insights from any timestamp
   - **Precision Timestamps**: Click any note to jump directly to that moment in the video
   - **Knowledge Vault**: Search and manage your entire library of captured insights
   - **Universal Export**: Export notes to Markdown, PDF, or Notion
   - **Rich Metadata**: Thumbnails, channel info, view counts, and duration tracking

**2. Wiz - Conversational Video Intelligence**
   - **Semantic Search**: Ask questions in plain English, get expert answers
   - **Context-Aware**: Wiz understands the video content and watches alongside you
   - **Deep Jump-Links**: Click on answers to play the exact video moment
   - **Vault Access**: Query across your entire video library
   - **Custom AI Integration**: Use your own OpenAI or Gemini API key

### Multi-Platform Access
   - **Browser Extension**: Works with any Chromium-based browser (Chrome, Edge, Brave, etc.)
   - **Web Dashboard**: Modern glassmorphic UI for managing notes and videos
   - **Android**: Integration via Macrodroid macros
   - **iOS**: Integration via Shortcuts automation

### Privacy & Control
   - **Self-Hosted**: Full control over your data with your own backend
   - **Enhanced Security**: No third-party data sharing
   - **Configurable AI**: Choose your AI provider and manage API keys

## Architecture

VidWiz uses a modern cloud-native architecture for scalability and performance:

```
Clients (Extension/Web/Mobile)
    ↓
Flask REST API
    ↓
PostgreSQL ←→ AWS Services
                  ├─ SQS (Async task queues)
                  └─ S3 (Storage)
```

**AWS Integration**:
- **SQS (Simple Queue Service)**: Handles asynchronous AI note generation and video summarization tasks
- **S3 (Simple Storage Service)**: Stores generated artifacts and processed outputs
- **Lambda-ready**: Backend includes Lambda functions for serverless processing

> **Note**: AWS services are used for async processing to prevent blocking the main application flow. AI note generation can take several seconds, so tasks are queued via SQS and processed asynchronously.

## Quick start (Docker Compose)
Prereqs: Docker, Docker Compose

1) Create a .env file with at least:

```
# App
DB_URL=postgresql://postgres:postgres@database:5432/vidwiz
SECRET_KEY=change-me
ADMIN_TOKEN=change-admin-token

# AWS
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=ap-south-1
SQS_AI_NOTE_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/123456789012/vidwiz-ai-notes
SQS_SUMMARY_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/123456789012/vidwiz-summary
S3_BUCKET_NAME=vidwiz

# AI/LLM
GEMINI_API_KEY=your-gemini-api-key

# Postgres container
POSTGRES_DB=vidwiz
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

2) Start services:
- Development: docker compose up -d --build → API at http://localhost:5000

## Local development
Prereqs: Python 3.10–3.13, Node.js, Poetry, running PostgreSQL

### Backend
1. `cd backend`
2. Install dependencies: `poetry install`
3. Configure `.env` (use `.env.example` as reference)
4. Start server: `python wsgi.py`

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
├── backend/              # Flask API
│   ├── vidwiz/
│   │   ├── routes/      # API endpoints
│   │   ├── lambdas/     # AWS Lambda functions
│   │   ├── services/    # Helper services
│   │   ├── shared/      # Utilities and models
│   │   └── tests/       # Pytest test suites
│   └── wsgi.py          # Flask entrypoint
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
- [ ] Cloud-hosted SaaS offering with subscription model

## Demo

<video src="https://github.com/user-attachments/assets/your-video-id/vidwiz.mp4" controls></video>

*Demo video: [vidwiz.mp4](frontend/src/public/vidwiz.mp4)*

## Screenshots

### Smart Notes Feature
![Smart Notes](frontend/src/public/smart-notes.png)
*Rich note-taking with timestamp navigation and video metadata*

### Ask Wiz - AI Assistant
![Ask Wiz](frontend/src/public/wiz.png)
*AI-powered note generation and intelligent assistance for your learning journey*

### Extension
<img width="369" height="450" alt="Screenshot 2026-01-16 011711" src="https://github.com/user-attachments/assets/d52c10c5-fcaa-4d0b-8dae-e2f63b7c2f66" />

