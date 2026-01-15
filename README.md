# VidWiz

## Description
VidWiz is designed to enhance your YouTube learning and note-taking experience. It allows you to capture and organize your thoughts while watching YouTube videos/lectures/video essays, with a special focus on timestamp-based note-taking. The extension integrates seamlessly with YouTube's interface, making it easy to save notes at specific moments/timestamps in videos.

Additionally, it leverages AI to automatically generate comprehensive notes for any timestamp, providing intelligent summaries and insights from the video content at that specific moment.

The extension is built with:
- Frontend: **React (Vite)** with **TypeScript** and **Tailwind CSS**
- Backend: **Flask (Python)** for REST API
- Database: **PostgreSQL** for data storage
- LLM: OpenAI/Gemini models for intelligent note generation

[Check Screenshots](#screenshots)

## Features
1. **Multi-Client Support**
   - Use the extension with any Chromium-based browser.
   - Use with Android devices via Macrodroid macros.
   - Use with iOS devices via Shortcuts automation.

2. **Interactive Dashboard**
   - A glassmorphic UI with a consolidated view of all your notes.
   - **Enhanced Video Details**: Rich metadata including thumbnails, channel info, view/like counts, and durations.
   - **Smart Navigation**: Open videos directly at the precise note timestamp.
   - **Fluid Interaction**: Seamless note CRUD with real-time feedback and modern transitions.

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

## Roadmap
- [x] Better UI/UX for Dashboard
- [x] Improve note CRUD functionality
- [x] AI generated note
- [x] Lambda workflow optimization
- [x] SQS Implementation
- [x] UI/UX Improvements
- [ ] Cloud Hosted Offering - Subscription model   

## Screenshots

### Dashboard
<img width="1280" height="900" alt="Screenshot 2026-01-16 011505" src="https://github.com/user-attachments/assets/52de59e9-b19b-46db-a22b-64f1652c58a0" />

### Video Notes
<img width="1280" height="900" alt="Screenshot 2026-01-16 011644" src="https://github.com/user-attachments/assets/365917cf-4c58-41a8-adb5-60d84a5b2a7b" />


### Extension
<img width="369" height="450" alt="Screenshot 2026-01-16 011711" src="https://github.com/user-attachments/assets/d52c10c5-fcaa-4d0b-8dae-e2f63b7c2f66" />


### Mobile View
<img width="422" height="816" alt="Screenshot 2026-01-16 011748" src="https://github.com/user-attachments/assets/acd8755c-bf89-4223-919d-6fe56602e189" />




