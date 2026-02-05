# VidWiz Extension

## Purpose
Document the Chromium extension that captures timestamped YouTube notes and sends them to the VidWiz API using a long-term token.

## Structure
- **Manifest**: `extension/manifest.json` (MV3)
  - Permissions: `activeTab`, `storage`, `scripting`
  - Host permissions: `<all_urls>`
- **Popup UI**: `extension/popup.html`, `extension/popup.css`, `extension/popup.js`

## Configuration
- `extension/popup.js` hard-codes:
  - `AppURL = https://vidwiz.online`
  - `ApiURL = https://api.vidwiz.online/v2`

## Key Flows
- **Token setup**: Stored in extension `localStorage` under `notes-token`.
- **Video detection**: Only supports `youtube.com/watch` pages. The popup reads title and current timestamp from the DOM via injected scripts.
- **Note capture**: `POST /v2/videos/{video_id}/notes` with Bearer long-term token. Payload: `{ video_title, timestamp, text | null }`.
- **Notes existence check**: `GET /v2/videos/{video_id}/notes` is used to detect existing notes.
- **Dashboard links**: Opens `/dashboard` or `/dashboard/{video_id}` in a new tab.

## Constraints
- Timestamp/title extraction depends on YouTube DOM selectors and can break.
- Shorts, live URLs, and `youtu.be` links are not currently handled by the popup logic.
- Only `www.youtube.com/watch` URLs are accepted (query param `v` required).
