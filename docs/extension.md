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
- `capture-bridge.js`: the web capture connection and command acknowledgements.
- `content.js`: reads the video ID (`/watch?v=` and `/shorts/`), title, channel, and
  current time from the main player, and whether an ad is playing; seeks the
  player; shows a toast in a shadow root. The toast sits inside the player, top
  right, in normal, theatre, and fullscreen mode, and centred below the
  controls on Shorts. In the miniplayer, or without a visible player, it sits at
  the window's bottom left.
- `popup.html`, `popup.css`, `popup.js`: Save moment with an optional note and
  the save options menu, plus the video's moments with click-to-play.
- `tooltip.js`: the popup's one shared tooltip, shown on hover and keyboard
  focus.
- `build.mjs`: writes a build with other origins, and zips it for the store.
  `output.mjs` decides whether an `--out` folder is safe to replace.

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
  toast: saved, merged into a nearby moment, or the error. Errors stay 6
  seconds instead of 2.6. During an ad it
  saves nothing and says to wait for the ad to end. Without a login it opens
  the web login page, at most once a minute. On a YouTube video tab that has no
  content script yet, it shows a red `!` badge whose tooltip asks for a reload.
- **Capture on the web** (3.0.1+): a signed-in web video page opens a named
  runtime connection through the existing `externally_connectable` origin.
  Capabilities and connections require the exact origin, a tab ID, and frame
  zero. The background worker forwards the capture command to the active
  VidWiz video tab; the web page uses its own player time, session, draft,
  and AI default to save. Other web routes do nothing. A video page without
  a connection gets a reload badge. YouTube capture still uses the content
  script and the extension API client.
  The handshake reports `commands.getAll()`'s actual shortcut; an empty
  assignment stays empty. Commands wait for their acknowledgement or a
  30-second timeout before another can be sent. A timeout never retries the
  save. Replaced or disconnected ports cannot receive new captures.
  Worker-initiated disconnects remove the connection and its timer immediately;
  Chrome only sends the disconnect event to the other end of the port.
- **Popup**: shows the login view, an idle view off YouTube videos, a reload
  view on video tabs without the content script, or the capture view.
  - The video card opens the video in VidWiz. It shows a 64×36 thumbnail,
    a two-line title, and the channel when available. Its tooltip says "Open
    video in VidWiz", after the full title or channel when the card cuts
    them short. Failed thumbnails are
    hidden so the text uses the full width. Channel names are display-only
    and are not sent in capture requests. A subtle divider separates the video
    details from the capture controls.
  - The compact header shows the profile picture, or the name's first letter,
    when the capture view has loaded a profile. Its tooltip and label show the
    name, credit balance, and "Open Settings", refreshed after saves; clicking
    it opens Settings.
    Without a profile the chip is hidden. The "Open VidWiz" header link
    appears only outside the capture view, never alongside the chip.
  - **Save moment** follows the user's AI line default and shows the video's
    current time, updated while it plays. It saves at the time of submitting.
    The arrow beside it opens the same options as the web app: "With AI line,
    1 credit" and "Without AI line, Free", with the default checked, and a link
    to change the default in Settings. Until the profile loads, the arrow shows
    but is disabled, so Save moment keeps its width. The moments load
    alongside the profile. While the options are open, the popup grows to
    fit them. Saving is disabled while an ad plays.
    Save moment's tooltip says what it will do: with an AI line for 1 credit,
    without one (the default, or because no credits are left), saving, paused
    for an ad, or "your AI line default" before the profile loads. Saving
    works before then too, with the server applying the default. The menu
    items save right away ("Save this moment with an AI line", or without);
    they don't change the default.
  - The note icon ("Add note", or "Edit note" while the field is open) beside
    Save moment opens and focuses an optional note field
    above the buttons. It starts as one line and grows to five. Enter submits;
    Shift+Enter adds a line. Clicking the icon again focuses the existing draft.
    Cancel note clears and closes it. A successful save clears and closes the
    field; a failed save keeps the draft open. Note controls are disabled while
    saving so a completed request cannot erase new edits.
  - After a save, the popup says "Moment saved at m:ss" (or "Added to your
    moment near m:ss") for 3 seconds, and the list scrolls to that moment.
    Like the web app's arrivals, the row gets a soft yellow tint, with no
    edge, for 2.5 seconds after it first appears, then fades out over 900 ms;
    with reduced motion it clears without fading. List refreshes continue the
    same timing, and every save or merge starts it again. Rows are inset 10px,
    so the tint stays inside the list. Errors stay until the next save.
  - Credits, from the profile's balance and re-read after each save: the menu
    shows "1 credit · N left", or "No credits" at zero. With no credits and the
    AI line as the default, a notice above Save moment says saves won't get an
    AI line and links to buying credits; saving still works. A moment that
    missed its AI line for lack of credits shows that in the warning colour.
  - The popup stays within Chrome's 600 px limit: only the moments list
    scrolls, under a count of the video's moments. Content sits 10px from
    each divider and from the popup's bottom.
  - Each moment has the web app's "…" menu with **Add note** or **Edit
    note**, and **Delete**. It opens below the button, or above it near the
    popup's bottom, stays inside the popup rather than the scrolling list,
    and closes on Escape, Tab, a click outside, focus leaving it, or scrolling;
    Home and End jump to the first and last item. The note is edited
    in the row (Enter saves, Shift+Enter adds a line, Esc cancels, empty
    removes it) with
    `PATCH /v2/moments/{id}`. Delete asks inside the row first, since there is
    no undo, then calls `DELETE /v2/moments/{id}`. While that request is out,
    the row stays as it is: repeated Enter, Esc, and other rows' actions wait
    for it. Errors show in the row and keep the draft for a retry. Cancel or
    Esc returns focus to the row's "…" button; after a delete it moves to the
    row that took its place. Enter never submits while an input method is
    composing, and Esc in the capture note works like Cancel note.
    While a row is being edited or confirmed, the list doesn't refresh, so
    nothing being typed is lost. A refresh already loading is discarded and
    fetched again afterwards, so it can't undo the edit or delete either.
  - If the tab moves to another video while the popup is open (autoplay or
    navigation), or leaves the video, the popup reloads for what the tab shows
    now, so a save never lands on a video other than the one shown.
  - **Moments**: each row shows the save time, and its time button plays from
    5 seconds before it, like the web app; its tooltip names that time ("Play
    from m:ss"). The text is the note, AI line, or
    quote, with the AI line's status in the web app's words when it is pending,
    failed, out of credits, or impossible without a transcript. Like the web
    app, only "Writing the AI line…" has a spinner, which stays still under
    reduced motion. The list refreshes every 3 seconds while an AI line is
    pending, for up to 3 minutes; each refresh keeps keyboard focus on the same
    row and control, or on the row's "…" button if its menu was open. If the
    list fails before anything has loaded, it offers Try again, which keeps
    focus when it fails again and moves it to the first moment when it loads.
- **Tooltips and cursors**: the brand, profile chip, video card, Save moment,
  its arrow ("Save options"), the note icon, the save menu items, time
  buttons, "…" ("Moment actions"), and the AI line mark ("AI-generated line")
  have tooltips. Controls whose text already says what they do have none.
  Tooltips show after a short hover or at once on keyboard focus, close on
  Escape, a click, or when the pointer leaves, and can be hovered. They sit
  outside the scrolling list, beside a menu rather than over its items, and
  inside the popup's edges; they close when their control is redrawn,
  hidden, or scrolled away. Links and enabled buttons use the pointer cursor,
  including their icons and text; disabled buttons use the default cursor
  and have no hover styles. Moment text stays selectable.
- **First install**: opens the web app, which syncs an existing login.

## Builds
- Production: load `extension/` unpacked, or run `node extension/build.mjs`
  (output in `extension/dist/prod`, ignored by Git) to package it. Add `--zip`
  to also write `extension/dist/vidwiz-extension-<version>.zip` for the Chrome
  Web Store; this needs the `zip` command.
- Windows: the unpacked build works the same. Windows has no `zip` command, so
  `--zip` stops with a message after building. Make the store zip on Linux or
  macOS and copy it over.
- Development: `node extension/build.mjs --web <web origin> --api <api base
  URL> --out extension/dist/dev`, then load that folder unpacked. Run the web
  app with `VITE_EXTENSION_ID` set to the unpacked extension's ID so login sync
  reaches it.
- `--out` is deleted and rewritten on every build. It must be under
  `extension/dist/` or outside `extension/`. The builder refuses the source
  folder, any folder that contains it, `dist/` itself, and an existing folder
  with files that is not an earlier VidWiz build. A folder with `build.mjs`,
  such as another checkout's `extension/`, never counts as a build. Symlinked
  parent folders are followed before these checks.

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

## Capture bridge release and validation

Deploy web bridge support before releasing extension 3.0.1. Older extensions
still reserve their shortcut and cannot forward it to the web; update the
extension, then reload the video page. No backend release or additional host
permissions are needed. Standalone web shortcuts cannot receive keys while
the cross-origin YouTube iframe has focus.

Run `node --test extension/output.test.mjs extension/capture-bridge.test.mjs extension/arrival.test.mjs`
and the frontend capture shortcut and CaptureBar tests. Browser acceptance
must use Chrome with the new unpacked extension and a matching web build:
check YouTube and web capture, two video tabs, iframe focus, editing, menus,
remapped and unassigned shortcuts, worker restart, page navigation, and the
extension disabled. Confirm each accepted command saves once at the current
player time. Use a test account and mocked capture responses for browser
checks; do not create production moments as test fixtures.
