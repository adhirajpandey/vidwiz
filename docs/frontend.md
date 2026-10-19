# VidWiz Frontend

## Purpose
Summarize the web app structure, routing, and API integration.

## Stack
Vite, React 19, TypeScript, Tailwind CSS 4, React Router, TanStack Query for
server state, Radix primitives (dialog, dropdown menu, tabs), cmdk for the
command palette, and assistant-ui for the chat thread. Deployed to Cloudflare
Workers.

## Structure
- `src/main.tsx`: providers (Helmet, TanStack Query, router, toasts, error
  boundary, session-expiry handler) and extension auth sync.
- `src/App.tsx`: routes. The video and Ask pages are lazy-loaded because they
  carry the chat and Markdown libraries.
- `src/app/`: the app shell (header, mobile bottom navigation, account menu),
  the command palette, and the query client.
- `src/features/<area>/`: pages and their components and queries:
  `home`, `library`, `search`, `video`, `ask`, `moments`, `chat`, `settings`,
  `auth`, `landing`, `share`. Pure helpers live in their own `.ts` files so
  component files only export components.
- `src/components/ui/`: small primitives (Button, Input, Tabs, Dialog, Menu,
  TimeChip, Thumbnail, EmptyState, ErrorState, Spinner, Toast).
- `src/components/wiz/`: the chat thread, Markdown rendering with citations,
  and the YouTube player.
- `src/api/`: the fetch wrapper, SSE reader, error normalization, types, and one
  module per backend domain (`moments`, `library`, `search`, `videos`,
  `conversations`, `auth`, `payments`).
- `src/hooks/`: `useWizChat` (chat transport and state), `useSignedIn`,
  `useProfile`, `useTheme`, `useNotify`, `useToast`.

## Routes
- `/`: Home when signed in (search on mobile, add a video, Ask entry, continue
  watching, recent moments grouped by day and video); the landing page when
  signed out.
- `/v/:videoId`: the video workspace. Query parameters: `t` (start playback at
  seconds), `m` (highlight a moment), `c` (resume a conversation), `tab`
  (`moments`, `ask`, `transcript`, `overview`).
- `/library`, `/search?q=`, `/ask` (`c` resumes, `q` asks once), `/settings`.
- `/login`, `/signup` (`next` returns to an in-app path), `/share` (PWA share
  target), `/privacy`.
- Redirects keep 2.x links working: `/dashboard` → `/library`,
  `/dashboard/:id` → `/v/:id`, `/wiz/:id` → `/v/:id?tab=ask`, `/profile` →
  `/settings`.

## Design
- Tokens in `src/index.css`: one accent (violet), flat surfaces, thin borders,
  and identical layouts in light and dark themes (`.dark` on `<html>`, chosen
  in `localStorage.theme` or from the OS).
- Geist for text and Geist Mono for times.
- Every paid action shows its cost: "AI line · 1 credit" when capturing,
  "Unlock · 5 credits" before the first question about a video.

## Key Behavior
- **Auth**: the JWT is stored in `localStorage`, validated on read, and sent by
  the fetch wrapper. `setToken` and `removeToken` sync the extension and emit an
  auth-change event that `useSignedIn` subscribes to. A `401` on an
  authenticated request triggers one session-expired notice and a redirect to
  `/login`.
- **Server state**: TanStack Query. Moment lists poll every 5 seconds while a
  moment is resolving, queued, or waiting for a transcript; the video polls
  while its `transcript_status` is `pending` or its `overview_status` is
  `queued`, and the transcript while it is `pending`. Every job ends in an
  explicit state, so polling always stops.
  Mutations invalidate moments, the library, and the profile (credit balance).
- **Moments**: `MomentItem` shows the AI line, the user's note, the quote, and
  one explicit status line with its fix (retry without a new charge, get
  credits). Title captures still resolving show a placeholder; ambiguous ones
  show the candidate videos to pick from.
- **Overview**: rendered from `overview_status`: writing, failed with a free
  retry (signed in), no transcript, or pending. While a newer overview is
  written or after it fails, the older one stays visible with a status line.
- **Video workspace**: the player is sticky on desktop and above the tabs on
  mobile. Captures use the player's current time. Timestamps in moments,
  key points, transcript lines, and citations seek the same player. The
  transcript highlights and follows the playing line, filters by text, and saves
  any line as a moment.
- **Ask**: `useWizChat` takes a target (`{scope: 'video', videoId}` or
  `{scope: 'library'}`), optionally resumes a conversation by loading its
  messages, and reports new conversation ids so the URL can hold them. A video
  conversation is created only after Ask is unlocked (`GET
  /videos/{id}/ask-status`), so opening the tab never charges. Citations in
  library answers carry `video_id`; they show the video title and open that
  video at the time. Every citation can be saved as a moment.
- **Guests**: the landing page starts a guest conversation for a pasted link
  and opens the workspace on the Ask tab.
- **Command palette**: ⌘K / Ctrl+K searches, asks the library, opens a pasted
  YouTube link, or jumps to a page.
- **PWA**: `public/manifest.webmanifest` with a share target; sharing a YouTube
  video to VidWiz saves and opens it.
- **API errors**: Fetch and SSE failures normalize to a shared error type. Safe
  handled `4xx` messages may be shown; `5xx` and malformed responses use curated
  copy and may include the backend `X-Request-ID`. Action failures use toasts;
  failed page or section loads render retry states.

## Development
- `pnpm dev` with `VITE_API_URL` pointing at an API (for example a local backend
  or a test deployment).
- `pnpm lint`, `pnpm test`, `pnpm build`.

## UI Screenshot Workflow
`scripts/screenshot_pages.py` captures the 2.x pages and still needs updating
for the v3 routes and states.
