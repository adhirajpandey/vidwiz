# VidWiz Extension

## Purpose
Document the Chromium extension that captures timestamped YouTube notes and sends them to the VidWiz API using auth synced from the web app.

## Structure
- **Manifest**: `extension/manifest.json` (MV3)
  - Permissions: `activeTab`, `storage`
  - Host permissions: YouTube + VidWiz API
  - `externally_connectable`: allows web app origin to send auth sync messages
- **Popup UI**: `extension/popup.html`, `extension/popup.css`, `extension/popup.js`
- **Background worker**: `extension/background.js` handles `onMessageExternal` auth sync (`SYNC_TOKEN`, `LOGOUT`)

## Configuration
- `extension/popup.js` hard-codes:
  - `BASE_URL = https://vidwiz.online`
  - `API_URL = https://api.vidwiz.online/v2`
- `extension/background.js` hard-codes allowed sender origin:
  - `ORIGINS.PROD = https://vidwiz.online`
- Web app must target the same installed extension ID:
  - `frontend/src/config.ts` -> `EXTENSION_ID`

## Key Flows
- **Auth sync**: Web app login/logout calls `chrome.runtime.sendMessage(EXTENSION_ID, ...)` to sync auth into the extension.
- **Token storage**: Extension stores token in `chrome.storage.local` under key `token`.
- **No manual token entry**: If token is missing, popup shows a "Log In to VidWiz" CTA that opens web login.
- **Video detection**: Only supports `youtube.com/watch` pages. The popup reads title and current timestamp from the DOM via injected scripts.
- **Note capture**: `POST /v2/videos/{video_id}/notes` with Bearer token from extension storage. Payload: `{ video_title, timestamp, text | null }`.
- **Notes existence check**: `GET /v2/videos/{video_id}/notes` is used to detect existing notes.
- **Dashboard links**: Opens `/dashboard` or `/dashboard/{video_id}` in a new tab.

## Constraints
- Timestamp/title extraction depends on YouTube DOM selectors and can break.
- Shorts, live URLs, and `youtu.be` links are not currently handled by the popup logic.
- Only `www.youtube.com/watch` URLs are accepted (query param `v` required).
- Web-to-extension auth sync requires:
  - matching extension ID in web config
  - matching allowed web origin in `manifest.json` and `background.js`
