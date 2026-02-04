# VidWiz Extension

## Purpose
Document the Chromium extension that lets users capture timestamped YouTube notes and send them to the VidWiz API using a long-term token.

## Scope
- Extension structure and permissions.
- Popup UI and its logic.
- How notes are captured and sent to the backend.

## Components
### Manifest
- `extension/manifest.json` (Manifest V3)
  - **Permissions**: `activeTab`, `storage`, `scripting`.
  - **Host permissions**: `<all_urls>`.
  - **Popup**: `popup.html`.

### Popup UI
- `extension/popup.html`: Token setup view + notes view.
- `extension/popup.css`: UI styling.
- `extension/popup.js`: Behavior and API calls.

## Key Flows
### 1) Token Setup
- Extension stores long-term token in `localStorage` under `notes-token`.
- If no token exists, the popup shows the setup view and prompts the user to get a token from `/profile`.

### 2) Video Detection
- On popup open, extension checks the active tab.
- If it's a YouTube watch page (`youtube.com/watch`), it:
  - Extracts the title from the DOM.
  - Extracts the current timestamp from the player.
- If not a YouTube watch page, the UI shows an error state.

### 3) Note Capture
- User enters text (optional) and clicks **Save Note**.
- Extension reads the video ID from the URL query param `v`.
- Timestamp is validated (must contain `:` and at least two digits).
- POST request is sent to:
  - `POST /v2/videos/{video_id}/notes`
  - Bearer token = long-term token
  - Payload: `{ video_title, timestamp, text | null }`

### 4) View Notes / Dashboard Links
- **View Notes**: Opens `/dashboard/{video_id}` in a new tab.
- **Dashboard**: Opens `/dashboard` in a new tab.

## Interfaces / Integration Points
- **Backend API**: `https://api.vidwiz.online/v2`.
- **Web App**: `https://vidwiz.online` for profile and dashboard links.
- **YouTube**: DOM scraping for title and current timestamp.

## Data / State (High-Level)
- **Token**: `notes-token` stored in extension `localStorage`.
- **Active tab data**: video title, timestamp, and video ID from URL.

## Operational Notes
- Extension requires a long-term token created in the web app profile.
- Timestamp extraction depends on YouTube's DOM selectors; changes can break extraction.
- Host permissions are broad (`<all_urls>`), but the extension only acts on YouTube watch pages.

## Open Questions
- Should the extension support Shorts, Live, or youtu.be URLs?
- Should the token be stored in Chrome storage instead of localStorage?

## Interaction Overview (ASCII)
```
User
  |
  v
Extension Popup
  |
  +--> Read YouTube DOM (title + timestamp)
  |
  +--> POST /v2/videos/{video_id}/notes
          (Bearer long-term token)
  |
  +--> Open Web App links
       - /profile (get token)
       - /dashboard/{video_id}
```
