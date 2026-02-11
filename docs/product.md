# VidWiz Product (PRD)

## Purpose
Define the product goals, user needs, and requirements for VidWiz.

## Problem
Learning from YouTube is friction-heavy: pausing, losing context, and poor note organization. VidWiz makes capture fast and chat grounded in the transcript.

## Goals
- Make timestamped capture effortless during playback.
- Provide transcript-grounded Q&A with citations.
- Support fast capture across web, extension, and mobile automations.
- Keep async transcript + AI processing reliable.

## Non-Goals (Current)
- Native mobile apps.
- Offline capture.
- Team collaboration.

## Target Users
- Students and self-learners.
- Professionals learning tools/workflows.
- Creators/reviewers taking timestamped notes.

## Core Use Cases
- Save a note at the current timestamp without leaving the video.
- Auto-generate a note when only a timestamp is provided.
- Ask questions about a video with transcript-based answers.
- Review notes by video and jump to timestamps.

## Functional Requirements
- **Auth**: Email/password and Google OAuth; extension auth sync from web login; long-term tokens for automations.
- **Notes**: Create, list, edit, delete; always timestamped.
- **Videos**: Store metadata + transcript availability; list/search; stream readiness.
- **Wiz Chat**: Conversation per video; transcript-only answers with timestamp citations; guest and user quotas.
- **AI Notes**: Generate when note text is empty, AI notes are enabled, and transcript is already available.
- **AI Summary**: Generate after transcript availability; optional display in video detail.

## Non-Functional Requirements
- Secure token handling.
- Low-latency note creation.
- Resilient async processing with retries.
- Clear error messages across clients.

## MVP Definition
- Web app: auth, dashboard, video detail, notes list, profile.
- Extension: web-login sync + note capture.
- Mobile automations: MacroDroid/Shortcuts capture flow.
- Transcript + metadata helpers.
- Wiz chat.
- AI notes + AI summary pipelines.

## Risks
- YouTube DOM changes can break extension capture.
- Transcript availability failures impact chat/AI.
- LLM hallucinations; mitigate with transcript-only prompts.

## Current Constraints (Product Reality)
- Web app does not provide note creation; notes are captured via extension/automations.
- Extension only supports `youtube.com/watch` pages (no Shorts/live/`youtu.be`).
- Extension depends on web-to-extension token sync; extension ID/origin mismatches block auth sync.
- Wiz chat depends on S3-hosted transcripts; if transcripts are missing, chat returns `processing` or errors.

## Open Questions
- Should the web app expose note creation directly?
- Should long-term tokens have scoped permissions?
- Do we need dedicated mobile clients beyond automations?
