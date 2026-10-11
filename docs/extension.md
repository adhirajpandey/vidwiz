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
- `extension/background.js` hard-codes the allowed sender origin (exact match on `sender.origin`):
  - `ORIGINS.PROD = https://vidwiz.online`
- Web app must target the same installed extension ID:
  - `frontend/src/config.ts` -> `EXTENSION_ID`

## Key Flows
- **Auth sync**: Web app login/logout calls `chrome.runtime.sendMessage(EXTENSION_ID, ...)` to sync auth into the extension. The web app also re-sends a valid token on every app load, so visiting the site re-syncs an extension that was installed later or holds an expired token.
- **Token storage**: Extension stores the web session JWT in `chrome.storage.local` under key `token`. It expires with the web session.
- **Expiry handling**: The popup decodes the token's `exp` on open and treats an expired or malformed token as logged out. A `401` from the API also clears the token. Both show a session-expired message on the login screen.
- **No manual token entry**: If token is missing, popup shows a "Log In to VidWiz" CTA that opens the web app, which re-syncs the token on load.
- **Video detection**: Only supports `youtube.com/watch` pages. The popup reads title and current timestamp from the DOM via injected scripts.
- **Note capture**: `POST /v2/videos/{video_id}/notes` with Bearer token from extension storage. Payload: `{ video_title, timestamp, text | null }`.
- **Dashboard links**: Opens `/dashboard` or `/dashboard/{video_id}` in a new tab.

## Constraints
- Timestamp/title extraction depends on YouTube DOM selectors and can break.
- Shorts, live URLs, and `youtu.be` links are not currently handled by the popup logic.
- Only `www.youtube.com/watch` URLs are accepted (query param `v` required).
- Web-to-extension auth sync requires:
  - matching extension ID in web config
  - matching allowed web origin in `manifest.json` and `background.js`
- Local development does not sync auth: the manifest only allows the production origin. To test locally, temporarily add the local web origin to `externally_connectable` and `background.js` without committing it.
