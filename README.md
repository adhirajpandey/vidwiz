# VidWiz

## Description
VidWiz is designed to enhance your YouTube learning and note-taking experience. It allows you to capture and organize your thoughts while watching YouTube videos/lectures/video essays, with a special focus on timestamp-based note-taking. The extension integrates seamlessly with YouTube's interface, making it easy to save notes at specific moments/timestamps in videos.

Additionally, it leverages AI to automatically generate comprehensive notes for any timestamp, providing intelligent summaries and insights from the video content at that specific moment.

The extension is built with:
- Frontend: HTML5, CSS3, and vanilla JavaScript for extension
- Backend: Flask (Python) for REST API
- Database: PostgreSQL for data storage
- LLM: OpenAI/Gemini models for intelligent note generation

## Features
1. **Multi-Client Support**
   - Use the extension with any Chromium-based browser.
   - Use with Android devices via Macrodroid macros.
   - Use with iOS devices via Shortcuts automation.

2. **Interactive Dashboard**
   - A modern UI with a consolidated view of all your notes.
   - Search for videos.
   - Open videos directly at the note's timestamp.
   - Edit and delete notes with ease.

3. **AI Magic**
   - Automatically generate accurate notes for any timestamp using LLMs.
   - Set your custom AI provider and API key.
   - Toggle the AI generation feature on or off.

4. **Self-Hosted**
   - Full privacy with a self-hosted backend.
   - Enhanced security over your data.
   - No third-party data sharing.

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
SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/123456789012/vidwiz
S3_BUCKET_NAME=vidwiz

# Postgres container
POSTGRES_DB=vidwiz
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

2) Start services:
- Development: docker compose up -d --build → API at http://localhost:5000

## Local development (Poetry)
Prereqs: Python 3.10–3.13, Poetry, running PostgreSQL

1) Install deps: poetry install
2) Export env vars (match .env above)
3) Run app (dev): poetry run vidwiz (runs Flask dev server on 0.0.0.0:5000)

## Extension setup
1) Load unpacked from extension/ in a Chromium browser (chrome://extensions → Developer mode → Load unpacked)
2) Configure backendEndpoint in extension/popup.js to your API base URL if self hosting
3) Generate a token for the extension:
    - Option A: JWT via POST /user/login (expires in 24h)
    - Option B: Long‑term token via POST /user/token (recommended)
4) In the extension popup’s DevTools console: localStorage.setItem('notes-token', '<your token>')

The popup reads the current YouTube title/timestamp and calls POST /notes.

## Running tests
- poetry run pytest

## Roadmap
- [x] Better UI/UX for Dashboard
- [x] Improve note CRUD functionality
- [x] AI generated note
- [x] Lambda workflow optimization
- [x] SQS Implementation
- [ ] Refine self-hosted setup
- [ ] Cloud Hosted Offering - Subscription model

## Screenshots

Dashboard

![dashboard-UI](https://github.com/user-attachments/assets/4136d26d-9a08-48ad-a1bd-d3c794fd37f6)

Video Notes

![notes-ui](https://github.com/user-attachments/assets/b6a9efb8-c69a-4406-91b3-bfe6cbce160b)

Extension

![extension-ui](https://github.com/user-attachments/assets/7d4f24ec-0acb-4a19-861c-4c4be093668b)

Mobile View

![mobile-ui](https://github.com/user-attachments/assets/f9b21644-a718-49e3-ab3e-666bc1bf7e4c)



