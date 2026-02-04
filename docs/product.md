# VidWiz Product Requirements Document (PRD)

## Purpose
Define the product vision, goals, user needs, and requirements for VidWiz. This PRD is a living document meant for engineers, agents, and future product planning.

## Scope
- Core problem and target users.
- Primary experiences: web app, browser extension, mobile automations.
- Functional requirements and non-functional requirements.
- MVP vs. next-phase roadmap.

## Background and Problem
Learning from YouTube is friction-heavy. Users pause frequently, lose context, and struggle to organize insights. Searching within long videos is slow, and notes lack context or timestamps. VidWiz solves this by enabling timestamped notes, AI-assisted summaries, and grounded video chat.

## Goals
- Reduce friction in capturing notes while watching videos.
- Make videos searchable and conversational with transcript-based AI.
- Support fast capture across web, extension, and mobile automations.
- Provide a reliable, scalable backend for async transcript and AI processing.

## Non-Goals (for now)
- Full native mobile apps.
- Cross-platform desktop apps.
- Offline note capture.
- Deep team collaboration features.

## Target Users and Use Cases
### Primary Users
- Students and self-learners who consume long educational videos.
- Professionals who learn tools/workflows from tutorials.
- Creators and reviewers who need quick timestamped notes.

### Key Use Cases
- Capture a note at the current timestamp without leaving the video.
- Auto-generate a note when the user saves a timestamp with no text.
- Ask questions about a video and get timestamped answers.
- Review all notes by video and jump to exact timestamps.

## Product Principles
- Minimal disruption to watching.
- Notes must always be tied to a timestamp.
- AI responses must be grounded in the transcript.
- Multiple capture surfaces, one consistent backend.

## Experience Overview
### Web App (Primary UI)
- Auth, dashboard, video detail, notes list, profile settings.
- Wiz chat experience for grounded Q and A.
- AI summaries and metadata visible in video detail.

### Browser Extension (Capture Surface)
- One-click notes from YouTube watch pages.
- Uses long-term token for API auth.
- Shows title and current timestamp in popup.

### Mobile Automations (Capture Surface)
- Android via MacroDroid; iOS via Shortcuts.
- Minimal capture flow: send timestamped note to API.
- Designed for rapid entry while watching on mobile.

## Functional Requirements
### Authentication
- Email/password and Google OAuth sign-in.
- JWT session tokens for web.
- Long-term token for extension and automations.

### Notes
- Create notes with timestamp and optional text.
- Associate notes with a video.
- Edit and delete notes.
- List notes by video.

### Videos
- Store video metadata and transcript availability.
- List videos by user, with search and pagination.
- Provide video detail view (metadata, summary, transcript status).
- Stream readiness state for metadata/transcript/summary.

### Wiz Chat
- Conversation per video, per viewer (user or guest).
- Transcript-based responses only.
- Timestamp citations in responses.
- Daily quota enforcement for guests and users.

### AI Notes
- If note is created without text and AI notes are enabled, generate a note via LLM.
- AI notes require transcript availability.

### AI Summary
- Generate and store summary after transcript is available.
- Summary is optional but recommended for the video detail view.

## Non-Functional Requirements
- Secure auth and token handling (no token exposure in logs).
- Low-latency note creation and retrieval.
- Resilient async processing with retries.
- Clear error messages across clients.
- Scalable transcript and AI processing pipelines.

## Success Metrics
- Note creation completion rate (web/extension/mobile).
- Median time to first note after opening a video.
- Percentage of notes created without manual text (AI-assisted).
- Wiz chat session length and retention.
- Transcript availability success rate.

## MVP Definition
- Web app with auth, dashboard, video detail, notes list, profile.
- Extension with token setup and note capture.
- MacroDroid/Shortcuts integration via long-term token.
- Transcript and metadata workers.
- Basic Wiz chat using transcript.
- AI notes and AI summary pipelines.

## Risks and Mitigations
- YouTube DOM changes break extension timestamp/title capture.
  - Mitigation: monitor and update selectors; fallback to manual input.
- Transcript availability failures.
  - Mitigation: retries, fallback messaging, and clear UI states.
- AI hallucinations or irrelevant answers.
  - Mitigation: enforce transcript-only system prompt.

## Open Questions
- Should we expose note creation directly in the web UI?
- Should long-term tokens support scoped permissions?
- Do we need dedicated mobile clients beyond automations?

## Interaction Overview (ASCII)
```
User
  |
  +--> Web App (auth, dashboard, video detail, Wiz)
  |
  +--> Extension (timestamped notes)
  |
  +--> Mobile Automations (timestamped notes)
         |
         v
     FastAPI /v2
       |
       +--> DB (users, videos, notes)
       +--> S3 (transcripts)
       +--> SQS (AI note/summary jobs)
```
