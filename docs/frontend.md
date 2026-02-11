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
- **Auth failure handling**: Axios interceptors clear tokens and redirect to `/login` on `401` (except on login/signup routes).
- **Guest sessions**: Wiz chat generates a `guestSessionId` in `sessionStorage` when no JWT exists; axios attaches `X-Guest-Session-ID` when present on all requests.
- **Wiz entry**: Rejects playlist URLs and normalizes to a clean video ID before routing.
- **Wiz chat**: Creates a conversation, streams video readiness from `/v2/videos/:id/stream`, and streams chat responses from `/v2/conversations/:id/messages` using `fetch` + manual SSE parsing.
- **Video readiness**: Uses a 60s stream timeout; on stream failure it falls back to polling `/v2/videos/:id` every 5s and shows a refresh prompt if transcript never becomes available.
- **Notes UI**: Notes can be edited/deleted in the web app; note creation is not exposed in the UI.
- **Dashboard search**: Uses `q` + pagination with `per_page=10`; shows results only after first search.
- **Profile**: Supports name updates, AI notes toggle, and long-term token create/revoke/copy for automation use cases.
- **Credits UI**: Profile shows available credits and a credit pack selector; checkout uses backend product list.
- **Theme**: Navbar toggle adds/removes `dark` on `documentElement` and stores the choice in `localStorage`; toggle is hidden on landing/login/signup.

## Config
- `frontend/src/config.ts` hard-codes `API_URL`, `GOOGLE_CLIENT_ID`, and `EXTENSION_ID` for dev/prod (no `.env` usage).
- Production `EXTENSION_ID` must be a real installed/store extension ID or token sync will fail.

## UI Notes
- Theme toggle adds/removes the `dark` class on `documentElement`.
- Tailwind tokens are defined via CSS variables in `frontend/src/index.css`.
