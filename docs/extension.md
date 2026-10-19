# VidWiz Extension

## Purpose
Document the Chromium extension that captures moments on YouTube and sends them
to the VidWiz API, using the login synced from the web app.

## Structure
Plain JavaScript modules, no bundler.
- `manifest.json` (MV3, version 3.x): `activeTab` and `storage` permissions;
  host access to YouTube and the API; the `capture-moment` command
  (default Alt+S); `externally_connectable` for the web app origin.
- `config.js`: web app and API origins for this build.
- `api.js`: token storage, the authenticated JSON client, and `capture()`.
  Shared by the popup and the background worker.
- `background.js` (module service worker): login and logout sync from the web
  app, the Alt+S capture, and opening the web app on first install.
- `content.js`: reads the video ID (`/watch?v=` and `/shorts/`), title, and
  current time; seeks the player; shows a toast in a shadow root on the page.
- `popup.html`, `popup.css`, `popup.js`: capture with an optional note and AI
  toggle, plus the video's moments with click-to-seek.
- `build.mjs`: writes a build with other origins.

## Key Flows
- **Login sync**: the web app sends `SYNC_TOKEN` and `LOGOUT` with
  `chrome.runtime.sendMessage` to the configured extension ID, and re-sends a
  valid token on every load. The background worker accepts messages only from
  the exact configured web origin and stores the session JWT in
  `chrome.storage.local`. Email and password logins work the same way as
  Google, which is how store reviewers sign in.
- **Expiry**: an expired or malformed token is treated as logged out. A `401`
  clears the token (unless a newer one was synced meanwhile) and shows the
  login view.
- **Alt+S**: the background worker asks the content script for the current
  video, posts `POST /v2/captures` with `video`, `title`, `at`, and
  `source: "extension"` (the AI line follows the user's default), and shows a
  toast: saved, merged into a nearby moment, or the error. Without a login it
  opens the web login page.
- **Popup**: shows the login view, an idle view off YouTube videos, or the
  capture view. A capture uses the video's time at the moment of submitting.
  The AI toggle starts from the user's default. Enter submits; Shift+Enter adds
  a line. The list shows the note, AI line, pending status, or quote for each
  moment, and its time button seeks the page's player.
- **First install**: opens the web app, which syncs an existing login.

## Builds
- Production: load `extension/` unpacked, or run `node extension/build.mjs`
  (output in `extension/dist/prod`, ignored by Git) to package it.
- Development: `node extension/build.mjs --web <web origin> --api <api base
  URL> --out extension/dist/dev`, then load that folder unpacked. Run the web
  app with `VITE_EXTENSION_ID` set to the unpacked extension's ID so login sync
  reaches it.

## Constraints
- Video detection and title reading depend on YouTube's page structure.
- Pages opened before the extension was installed or updated need a reload
  before the popup or Alt+S can read the video.
- The 2.x extension still posts to `POST /v2/videos/{video_id}/notes`; the API
  keeps that route until 3.x is live in the store.
