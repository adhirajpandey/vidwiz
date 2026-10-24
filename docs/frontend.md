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
- `/`: Home when signed in (search on mobile, add a video, a compact Recent videos strip,
  and recent moments grouped once per day and video); the landing page when
  signed out. The landing page renders without the app header and has its own
  styles in `features/landing/landing.css` (Bricolage Grotesque, light and dark
  from the app theme).
- `/v/:videoId`: the video workspace. Query parameters: `t` (start playback at
  seconds), `m` (highlight a moment), `c` (resume a conversation), `tab`
  (`moments`, `ask`, `transcript`, `overview`).
- `/library`, `/search?q=`, `/ask` (`c` resumes, `q` asks once), `/settings`.
- `/login`, `/signup` (`next` returns to an in-app path), `/share` (PWA share
  target).
- `/privacy` and `/support`: public text pages that share
  `features/landing/DocPage.tsx`. The landing footer, the account menu, and
  Settings link to them. They are the privacy policy and support URLs for the
  Chrome Web Store listing.
- Redirects keep 2.x links working: `/dashboard` → `/library`,
  `/dashboard/:id` → `/v/:id`, `/wiz/:id` → `/v/:id?tab=ask`, `/profile` →
  `/settings`.

## Design
- Paper theme, tokens in `src/index.css`: blue-ink text on cool white, flat
  surfaces, thin borders, and identical layouts in light and dark themes
  (`.dark` on `<html>`, chosen in `localStorage.theme` or from the OS).
- Ink (`accent`) carries actions: primary buttons, links, the active tab, focus.
- Caption yellow (`saved`) marks only what the user saved: timestamps, the Save
  moment button (`Button variant="save"`), the moment strip under the player,
  search matches, and citations. It is always a background behind ink text.
- AI text has no colour of its own; a small sparkle icon marks it.
- Bricolage Grotesque everywhere, with tabular digits for times. Headings use
  the `display` utility (condensed and heavy).
- Every paid action shows its cost: "Unlock for 5 credits" before the first
  question about a video, and the cost of each way to save in the save menu.
- The note field starts collapsed; the pencil opens it, and Cancel note or
  Escape closes it. Saving keeps the selected panel and shows an inline
  **View moment** toast action to open and highlight the saved moment.
- Save moment is a split button. The main part follows the AI line default from
  Settings. The arrow opens a menu listing both ways with their cost and key,
  the default checked (S); the other is Shift S. Choosing one saves.

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
- Moment timestamps and timeline marks use the saved capture time. Playing a
  moment starts five seconds earlier (clamped at zero), including search and
  exported links; the transcript quote has its own context window.
- **Library**: one field searches titles and channels or previews a pasted
  YouTube video link. Views select All, With moments, or With chats; their
  counts follow the search. A themed menu offers six sorts. A paste card
  checks membership, preserves the link's time, and offers Add and open or
  Add to library. Existing videos open directly; failed checks claim no
  membership state, and failed saves retry the original action in place.
- **Resurfacing**: Home shows an older moment in a stable daily order. Another
  advances through the eligible moments and wraps to the first. Empty results
  hide the section; failures show a retry. Imported moments use an approximate
  date label.
- **Home and video rows**: the four recent videos show thumbnail durations.
  Library rows separate channel, moment count, chats, activity, and the latest
  moment text. Feed groups follow capture order, with moments in video-time
  order inside each group. Quote-only moments keep their text preview.
- **Moment actions**: deleting asks inline before making a request. Escape or
  Cancel returns focus to the actions button. Only one row can edit a note or
  confirm deletion at a time; a failed delete stays open with a retry.
- **Moments**: `MomentItem` shows the AI line, the user's note, the quote, and
  one explicit status line with its fix (retry without a new charge, get
  credits). While the AI line is being written, its status takes the AI line's
  place. `MomentQuote` folds the quote behind "What was said" when the moment
  has an AI line or note, and otherwise shows a three-line preview with "Show
  all". The fold follows the content, so the quote folds away when the AI line
  arrives. Title captures still resolving show a placeholder; ambiguous ones
  show the candidate videos to pick from.
- **Overview**: rendered from `overview_status`: writing, failed with a free
  retry (signed in), no transcript, pending (transcript still loading), or
  no overview yet (transcript ready, never queued). While a newer overview is
  written or after it fails, the older one stays visible with a status line.
- **Video workspace**: desktop shows moments below the player and a separate
  scrolling column for Transcript (the default), Ask, and Overview. On phones,
  the player, moment strip, save controls, and tabs stay pinned. Windows under
  720px tall use page scrolling. Captures use the player's current time. Timestamps in moments,
  key points, transcript lines, and citations seek the same player. The
  transcript centers the playing line in its own scroll panel, with natural
  clamping at the start and end. Line changes ease over 240 ms; initial entry,
  large seeks, and reduced-motion preferences use immediate positioning.
  Manual scrolling pauses follow; "Follow playback" or a transcript timestamp
  resumes it. Searching suspends centering.
  The panel recenters on seeks, tab entry, and size changes while following,
  without scrolling the page. It also filters by text and saves any line as a
  moment.
- Overview questions fill the Ask composer without sending. Locked videos show
  the question above the unlock action and retain it after unlocking.
- Ask initializes only when its tab is first opened. It stays mounted after
  that so switching panels preserves the chat. Creating a conversation updates
  its URL parameter without changing the selected panel.
- **Ask**: `useWizChat` takes a target (`{scope: 'video', videoId}` or
  `{scope: 'library'}`), optionally resumes a conversation by loading its
  messages, and reports new conversation ids so the URL can hold them. A video
  conversation is created only after Ask is unlocked (`GET
  /videos/{id}/ask-status`), so opening the tab never charges. Citations in
  library answers carry `video_id`; they show the video title and open that
  video at the time. Every citation can be saved as a moment.
- **Guests**: the landing page starts a guest conversation for a pasted link
  and opens the workspace on the Ask tab.
- **Search links**: moment hits open Moments and highlight the saved moment;
  passage hits open Transcript. Playback requests made before player setup
  are queued and retain the existing lead-in and autoplay fallback.
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

## Tab titles
Tab titles name what is open, most specific first, joined with ` · ` and
ending in `VidWiz`. `documentTitle` in `src/lib/title.ts` builds them; public
pages pass the result to `Seo`, and signed-in pages use `PageTitle`.
- The landing page and `index.html` share `LANDING_TITLE`.
- A video page adds its open panel, as in `<video title> · Ask · VidWiz`.
  While the video loads, fails, or has no title yet, the title is
  `Video · VidWiz`; it never shows the video ID.
- A library chat is named by its first question, shortened, and keeps that
  name through follow-ups. A new chat is `Ask your library · VidWiz`.
- Search uses `"<query>" · Search · VidWiz` with curly quotes.

Chat controls are called **New chat** and **Chat history** everywhere.

## UI Screenshot Workflow
`scripts/screenshot_pages.py` captures the 2.x pages and still needs updating
for the v3 routes and states.

## Brand assets

Navigation, landing, and authentication pages use the primary SVG mark.
`index.html` declares the favicon and Apple icon; the manifest keeps standard
and maskable icons separate. The default social card is shared by Open Graph
and Twitter metadata, including page-specific titles from `Seo`.
See [Brand assets](branding.md) for the files, font provenance, and regeneration.
