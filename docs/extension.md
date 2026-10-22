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
  current time from the main player, and whether an ad is playing; seeks the
  player; shows a toast in a shadow root on the page, inside the fullscreen
  element when the player is fullscreen.
- `popup.html`, `popup.css`, `popup.js`: Save moment with an optional note and
  the save options menu, plus the video's moments with click-to-play.
- `build.mjs`: writes a build with other origins, and zips it for the store.

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
  toast: saved, merged into a nearby moment, or the error. During an ad it
  saves nothing and says to wait for the ad to end. Without a login it opens
  the web login page, at most once a minute. On a YouTube video tab that has no
  content script yet, it shows a red `!` badge whose tooltip asks for a reload.
- **Popup**: shows the login view, an idle view off YouTube videos, a reload
  view on video tabs without the content script, or the capture view.
  - **Save moment** follows the user's AI line default and shows the video's
    current time, updated while it plays. It saves at the time of submitting.
    The arrow beside it opens the same options as the web app: "With AI line,
    1 credit" and "Without AI line, Free", with the default checked, and a link
    to change the default in Settings. Saving is disabled while an ad plays.
  - Enter submits; Shift+Enter adds a line.
  - **Moments**: each row shows the save time, and its time button plays from
    5 seconds before it, like the web app. The text is the note, AI line, or
    quote, with the AI line's status in the web app's words when it is pending,
    failed, out of credits, or impossible without a transcript. The list
    refreshes every 3 seconds while an AI line is pending, for up to 3 minutes.
- **First install**: opens the web app, which syncs an existing login.

## Builds
- Production: load `extension/` unpacked, or run `node extension/build.mjs`
  (output in `extension/dist/prod`, ignored by Git) to package it. Add `--zip`
  to also write `extension/dist/vidwiz-extension-<version>.zip` for the Chrome
  Web Store; this needs the `zip` command.
- Development: `node extension/build.mjs --web <web origin> --api <api base
  URL> --out extension/dist/dev`, then load that folder unpacked. Run the web
  app with `VITE_EXTENSION_ID` set to the unpacked extension's ID so login sync
  reaches it.

## Constraints
- Video detection and title reading depend on YouTube's page structure.
- Pages opened before the extension was installed or updated need a reload
  before the popup or Alt+S can read the video; the popup and the badge say so.
- The player and ad detection use YouTube's `#movie_player`,
  `html5-main-video`, and `ad-showing` classes.
- The 2.x extension still posts to `POST /v2/videos/{video_id}/notes`; the API
  keeps that route until 3.x is live in the store.

## Branding

The 16, 48, and 128 px icons are generated from the same SVG as the web app.
The popup selects an outlined Bricolage wordmark for the OS light or dark
scheme, and uses the web app's palette for that scheme: ink for actions and
links, caption yellow for Save moment and time chips. Its text is set in
Bricolage Grotesque from `fonts/` (latin subset, SIL Open Font License), so
the popup makes no font request. The on-page toast copies the web app's
toast with system fonts. `build.mjs` copies `icons/` and `fonts/`.
See [Brand assets](branding.md) for regeneration.
