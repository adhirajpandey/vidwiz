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
- Capture a moment at the current time without leaving the video, from a phone, the extension, or the web.
- Get an AI line and the exact transcript quote for each moment.
- Ask questions about a video with transcript-based answers.
- Ask across the library, including about a period, such as what was saved this week.
- Review notes by video and jump to timestamps.

## Functional Requirements
- **Auth**: Email/password and Google OAuth; extension auth sync from web login; named personal API tokens, accepted only for captures, for automations.
- **Moments**: Capture, list, edit, delete; always timed. Nearby captures merge. Title-only captures resolve in the background.
- **Library**: Explicitly saved videos, including videos used only in chat.
- **Videos**: Store metadata + transcript availability; list/search; stream readiness.
- **Wiz Chat**: Conversation per video; transcript-only answers with timestamp citations; guest and user quotas.
- **AI Moments**: Generate when requested (or by the user's default), charged once per moment, with an explicit status.
- **AI Summary**: Generate after transcript availability; optional display in video detail.
- **Wiz starter questions**: Generate three transcript-grounded questions with
  each new summary and show them in the empty Wiz chat.

## Non-Functional Requirements
- Secure token handling.
- Low-latency note creation.
- Resilient async processing with retries.
- Clear error messages across clients.

## MVP Definition
- Web app: auth, home, library, video page with capture, search, Ask, settings.
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
- Capture works from the web player, the extension (watch pages and Shorts), and phone automations.
- Extension depends on web-to-extension token sync; extension ID/origin mismatches block auth sync.
- Wiz chat depends on S3-hosted transcripts; if transcripts are missing, chat returns `processing` or errors.

## Open Questions
- Do we need dedicated mobile clients beyond automations and the PWA share target?
