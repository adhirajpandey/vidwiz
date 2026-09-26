# VidWiz Frontend

## Purpose
Summarize the web app structure, routing, and API integration.

## Structure
- **Entry**: `frontend/src/main.tsx` sets up router, toast provider, and scroll handling.
- **Routes**: `frontend/src/App.tsx` defines routes and wraps them in `Layout`.
- **Layout**: `components/layout/*` provides navbar/footer and theme toggle.
- **API layer**: `frontend/src/api/*` wraps axios + domain APIs.
- **Auth utils**: `frontend/src/lib/authUtils.ts` manages JWT storage/expiry and headers, and syncs login/logout to the extension via `chrome.runtime.sendMessage`; `ProtectedRoute` gates authenticated routes.
- **Video parsing**: `frontend/src/lib/videoUtils.ts` accepts raw IDs and URLs (`watch`, `shorts`, `live`, `embed`, `youtu.be`) and rejects playlists.
- **Google Sign-In**: `components/GoogleSignInButton.tsx` wraps Google Identity Services and renders a custom-styled overlay.

## Routes (High Level)
- `/`: Landing
- `/login`, `/signup`: Auth
- `/dashboard`: Video list/search
- `/dashboard/:videoId`: Video detail + notes list
- `/profile`: Profile + AI notes toggle + long-term token management
- `/wiz`: Wiz entry
- `/wiz/*`: Wiz workspace (accepts raw video ID or full URL; normalizes to `/wiz/{videoId}`)

## Key Behavior
- **Auth**: JWT stored in `localStorage`, validated on read, and injected into axios requests.
- **Web-to-extension auth sync**: `setToken`/`removeToken` send `SYNC_TOKEN`/`LOGOUT` to the configured extension ID.
- **Auth failure handling**: Axios and Fetch requests emit one session-expired
  event on application `401` responses. The React session handler clears the
  token, shows one notification, and redirects to `/login`; credential failures
  on login/signup remain on their forms.
- **Guest sessions**: Wiz chat generates a `guestSessionId` in `sessionStorage` when no JWT exists; axios attaches `X-Guest-Session-ID` when present on all requests.
- **Wiz entry**: Rejects playlist URLs and normalizes to a clean video ID before routing.
- **Wiz chat**: Creates a conversation, streams video readiness from
  `/v2/videos/:id/stream`, and streams chat responses from
  `/v2/conversations/:id/messages` through the shared authenticated Fetch and
  SSE utilities.
- **Wiz chat UI**: The lazily loaded workspace uses assistant-ui ExternalStoreRuntime.
  `useWizChat` owns domain messages, conversation creation, authenticated SSE,
  quota/processing responses, and request identity without importing assistant-ui.
  `WizChat` converts domain messages at the UI boundary; assistant-ui owns the
  composer, message iteration, scrolling, and copy feedback. Sending is blocked
  throughout a run while typing remains available. The composer supports Enter
  to send and Shift+Enter for a newline.
- **Wiz lifecycle**: Each workspace entry creates a fresh server conversation.
  New chat clears the draft and thread, aborts the local stream, and creates a
  new conversation. Generation and request guards discard obsolete updates,
  including late errors and cleanup. Local abort does not promise cancellation
  of backend generation. FastAPI remains responsible for message persistence
  and history; the UI does not restore conversations after reload.
- **Wiz answers**: `useWizChat` streams ordered blocks with attached citations.
  Conversations saved before block answers still render their stored
  text/citation parts.
  Complete blocks render through assistant-ui Markdown with GFM and raw HTML
  disabled. Watch buttons attach to paragraphs or the cited top-level list item,
  including evidence for its nested content. Table, quote, and code references
  appear below the intact block. References use backend-grouped passage ranges;
  each button shows the source start time and exposes the full range accessibly.
  Timestamp-looking Markdown is ordinary text and is never parsed for seeking.
  Copy joins only text parts with blank lines. Partial answers survive stream
  failures; errors and support references render separately and are excluded
  from copying. A typed `done` event confirms persistence; EOF without a terminal
  event is an interruption. Edit, regenerate, branching, Stop, and history
  controls are not enabled.
- **Wiz playback**: The YouTube IFrame Player API seeks two seconds before the
  source, clamped to zero, and requests playback. It queues only the latest click
  before readiness and cancels pending work on video changes/unmount. An off-screen
  player scrolls into view, respecting reduced motion. Playback continues past the
  passage end. Player errors or a 10-second playback timeout show a timestamped
  YouTube fallback link; autoplay blocking also prompts the user to press Play.
  Transcript previews and text-level phrase anchors are not part of this version.
- **Wiz starter questions**: The empty chat renders three video-specific
  questions from `VideoRead.suggested_questions`. Clicking one fills the input;
  videos without generated questions show no generic fallback chips.
- **Video readiness**: Uses a 60s stream deadline and reconnects to the video SSE endpoint every 5s after failures. Shows a retry error for failed status checks or a processing prompt when the transcript is still unavailable. Check again restarts the deadline without leaving the conversation.
- **API errors**: Axios, Fetch, and SSE failures normalize to a shared frontend
  error type. Safe handled `4xx` messages may be shown to users; `5xx` and
  malformed responses use curated fallback copy and may include the backend
  `X-Request-ID` as a support reference.
- **Error presentation**: Field validation is inline, action failures use
  toasts, and failed page/section loads render persistent retry states. Loading
  failures are kept separate from legitimate empty results.
- **Runtime failures**: A root error boundary provides reload/home recovery for
  unexpected React render failures. No external frontend telemetry is
  configured.
- **Notes UI**: Notes can be edited/deleted in the web app; note creation is not exposed in the UI.
- **AI note pending state**: Video notes show a pending AI chip (`⏳`) and "Generating AI note..." placeholder when a note is empty, not yet AI-generated, and the user has AI notes enabled.
- **Notes polling**: The video page polls `/v2/videos/:id/notes` every 4 seconds only while pending AI notes exist, and stops polling automatically once all pending notes are resolved.
- **AI note edits**: Editing a note sends `generated_by_ai=false` with the note text update so edited AI notes are treated as user-authored.
- **Dashboard**: A responsive library with summary totals, three recently active videos,
  roomier rows, and activity/title sorting. Cards and rows show views and upload
  dates when available, softly violet-tinted Ask Wiz actions, and red-tinted Notes actions.
  Recent activity cards stack a full-width thumbnail, title/channel, video metadata,
  and two actions. Note counts and activity remain in the library rows.
  Library membership remains notes-based.
- **Dashboard search**: Searches titles and note text in separate sections, each
  controlled by an All/Videos/Notes scope dropdown. Scope defaults to All and is
  preserved in the `scope` URL parameter; changing scope resets result pages.
  Only the selected result types are fetched. Results are
  paginated by ten. URL parameters `q`, `videosPage`, and `notesPage` restore
  searches on reload/Back. Queries need at least two characters. Clearing returns
  to the library. Obsolete requests cannot overwrite newer results.
- **Note links**: Search results open `/dashboard/:videoId#note-:noteId`, scroll to
  and highlight the note after loading, or show a missing-note message.
- **Library activity**: Latest owned note creation/update or saved chat message,
  not a view or playback position. Chat totals exclude empty conversations and
  videos without the user's notes. AI totals count current AI flags.
- **Profile**: Supports name updates, AI notes toggle, and long-term token create/revoke/copy for automation use cases.
- **Credits UI**: Profile shows available credits and a credit pack selector; checkout uses backend product list.
- **Navbar credits**: Opening the authenticated avatar menu fetches the latest balance from `/users/me`. The Credits row links to the profile credit section and refreshes when the menu reopens or its browser window regains focus.
- **Theme**: Navbar toggle adds/removes `dark` on `documentElement` and stores the choice in `localStorage`; toggle is hidden on landing/login/signup.

## Config
- `frontend/src/config.ts` defaults API requests to `http://localhost:5000/v2` in development and `https://api.vidwiz.online/v2` in production. Set `VITE_API_URL` before starting Vite to override either default.
- `GOOGLE_CLIENT_ID` and `EXTENSION_ID` remain defined per environment in `frontend/src/config.ts`.
- Production `EXTENSION_ID` must be a real installed/store extension ID or token sync will fail.

## UI Notes
- Theme toggle adds/removes the `dark` class on `documentElement`.
- Tailwind tokens are defined via CSS variables in `frontend/src/index.css`.

## UI Screenshot Workflow
`scripts/screenshot_pages.py` uses Playwright to capture named routes as overlapping desktop and mobile viewport images. The workflow forces dark mode, uses anonymous contexts for public pages, and logs into the local API for protected pages. It does not start the frontend or backend.

The script declares its own dependencies inline. Install the matching Playwright
Chromium once, and again whenever the pinned Playwright version changes:

```powershell
uvx --from "playwright==1.61.0" playwright install chromium
```

Copy `scripts/.env.example` to `scripts/.env`, then provide an existing local account and a video ID whose metadata and transcript are ready. Process environment variables take precedence over values in that file. Credentials are used only for `POST /v2/auth/login` and are not printed.

Common commands from the repository root:

```powershell
uv run scripts/screenshot_pages.py --list
uv run scripts/screenshot_pages.py --pages landing dashboard --sizes mobile desktop
uv run scripts/screenshot_pages.py --all --sizes mobile desktop --browser-mode headless
```

Generated PNGs default to `scripts/outputs/ui-images/` and are ignored by Git. Before each page capture, older numbered images for the same page and size are removed. Opening the Wiz workspace follows the real application behavior and creates an empty local conversation, but the script never sends a chat message.
