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
- `content.js`: reads the video ID (`/watch?v=` and `/shorts/`), title, channel, and
  current time from the main player, and whether an ad is playing; seeks the
  player; shows a toast in a shadow root. The toast sits inside the player, top
  right, in normal, theatre, and fullscreen mode, and centred below the
  controls on Shorts. In the miniplayer, or without a visible player, it sits at
  the window's bottom left.
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
  - The video card opens the video in VidWiz. It shows a 64×36 thumbnail,
    a two-line title, and the channel when available. Failed thumbnails are
    hidden so the text uses the full width. Channel names are display-only
    and are not sent in capture requests. A subtle divider separates the video
    details from the capture controls.
  - The compact header shows the profile picture, or the name's first letter,
    when the capture view has loaded a profile. Its tooltip shows the name
    and credit balance, refreshed after saves; clicking it opens Settings.
    Without a profile the chip is hidden. The "Open VidWiz" header link
    appears only outside the capture view, never alongside the chip.
  - **Save moment** follows the user's AI line default and shows the video's
    current time, updated while it plays. It saves at the time of submitting.
    The arrow beside it opens the same options as the web app: "With AI line,
    1 credit" and "Without AI line, Free", with the default checked, and a link
    to change the default in Settings. Saving is disabled while an ad plays.
  - The note icon beside Save moment opens and focuses an optional note field
    above the buttons. It starts as one line and grows to five. Enter submits;
    Shift+Enter adds a line. Clicking the icon again focuses the existing draft.
    Cancel note clears and closes it. A successful save clears and closes the
    field; a failed save keeps the draft open. Note controls are disabled while
    saving so a completed request cannot erase new edits.
  - After a save, the popup says "Moment saved at m:ss" (or "Added to your
    moment near m:ss") for 3 seconds, and the list highlights that moment and
    scrolls to it. Errors stay until the next save.
  - Credits, from the profile's balance and re-read after each save: the menu
    shows "1 credit · N left", or "No credits" at zero. With no credits and the
    AI line as the default, a notice above Save moment says saves won't get an
    AI line and links to buying credits; saving still works. A moment that
    missed its AI line for lack of credits shows that in the warning colour.
  - The popup stays within Chrome's 600 px limit: only the moments list
    scrolls, under a count of the video's moments.
  - Each moment has the web app's "…" menu with **Add note** or **Edit
    note**, and **Delete**. The note is edited in the row (Enter saves,
    Shift+Enter adds a line, Esc cancels, empty removes it) with
    `PATCH /v2/moments/{id}`. Delete asks inside the row first, since there is
    no undo, then calls `DELETE /v2/moments/{id}`. Errors show in the row.
    While a row is being edited or confirmed, the list doesn't refresh, so
    nothing being typed is lost.
  - If the tab moves to another video while the popup is open (autoplay or
    navigation), the popup reloads for that video, so a save never lands on a
    video other than the one shown.
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
The popup header uses the web app's lockup: the colour mark from
`frontend/public/brand/` and the name as Bricolage text. The popup uses the web app's palette for that scheme: ink for actions and
links, caption yellow for Save moment and time chips. Its text is set in
Bricolage Grotesque from `fonts/` (latin subset, SIL Open Font License), so
the popup makes no font request. The on-page toast copies the web app's
toast with system fonts. `build.mjs` copies `icons/` and `fonts/`.
See [Brand assets](branding.md) for regeneration.
