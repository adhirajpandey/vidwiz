# VidWiz Frontend

## Purpose
Summarize the web app structure, routing, and API integration.

## Stack
Vite, React 19, TypeScript, Tailwind CSS 4, React Router, TanStack Query for
server state, Radix primitives (dialog, dropdown menu, tabs), cmdk for the
command palette, and assistant-ui for the chat thread. Deployed to Cloudflare
Workers.

## Structure
- `src/main.tsx`: browser routing, hydration of pre-rendered pages, and
  extension auth sync. `src/app/AppContent.tsx` shares the query, toast, tooltip,
  and error providers between the browser and build-time renderer.
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
  signed out. The landing page renders without the app header and is always
  dark, whatever the app theme. It shows real recordings served from
  `public/landing/`: the Chrome extension saving on YouTube (Alt+S in
  fullscreen, then the moment in the extension's popup), and the app from a demo
  account (desktop and phone cuts of Save and Search). The "Save from wherever
  you watch" ways switch the recording beside them; phones show them as tabs
  above it, with the chosen way's description below. Each recording loads as it nears the
  screen, plays muted while visible, and pauses on tap; with reduced motion it
  waits for a tap. A recording can carry time cues, data attributes that follow
  its playback, for the pressed keys and the zoom onto the extension's toast. CSS
  shows the phone recordings below 760px and the desktop ones above. Its Ask example is a real
  answer whose citations play the source on YouTube from the cited second. Its
  styles are in `features/landing/landing.css`, scoped to `.landing`.
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
- Arrivals are highlights that point at what you just reached: a moment
  opened from View moment, search, Home, Resurface, or a link with `m`, and a
  video just added in the Library. The row gets a 9% caption-yellow tint with
  no edge for 2.5 seconds after it is first shown, then fades out over 900 ms;
  reduced motion clears it without fading (`lib/arrival.ts`,
  `hooks/useArrival.ts`). Polling, rerenders, and remounts continue the same
  timing. View moment and links to the same moment replay it; switching
  panels does not. The list scrolls to an arrival once. State highlights
  (the playing transcript line, the open chat, the chosen sort, search
  matches, the new API token) follow their state and never fade.
- Icon-only controls get a hint from the shared `Tooltip`
  (`components/ui/Tooltip.tsx`, Radix): ink inverted from the theme, small
  semibold text, shown after 400 ms of hover or at once on keyboard focus,
  and closed by Escape. Focus returned by a click or a closing menu doesn't
  show it. Controls whose text says what they do have none, and nothing uses
  the browser's `title`. Fields and the chat composer share the buttons' 2px
  focus outline.
- Cursors follow what a thing does, from shared rules in `src/index.css`:
  links and enabled controls (buttons, menu items, tabs, time chips, timeline
  markers) show a pointer. Disabled or busy controls keep the arrow, and the
  `hover` variant skips them, so they don't change on hover. Transcript,
  answers, notes, and fields keep the text cursor; standalone counts and status
  lines use the arrow. The landing page's recordings and citations are controls,
  so they show a pointer.
- Bricolage Grotesque everywhere, with tabular digits for times. Headings use
  the `display` utility (condensed and heavy).
- Every paid action shows its cost: "Unlock for 5 credits" before the first
  question about a video, and the cost of each way to save in the save menu.
- The note field starts collapsed; the pencil opens it, and Cancel note or
  Escape closes it. Enter saves the note with the moment; Shift+Enter adds a line.
  Saving keeps the selected panel and shows an inline
  **View moment** toast action to open the saved moment and show it as an
  arrival.
- Save moment is a split button. The main part follows the AI line default from
  Settings. The capture shortcut saves with that default. The arrow opens a
  menu listing both ways with their cost; the default is checked and shows the
  current shortcut. Choosing one saves. At zero
  credits, the default AI save shows a notice and existing moments offer
  Get credits instead of Add AI line.
  Saves wait for a ready player and never guess a timestamp.
- **Capture shortcut**: without the extension, Alt+S works while focus is in
  the web page. With extension 3.0.1 or newer, `useCaptureShortcut` opens a
  `vidwiz-capture-v1` runtime connection. The extension forwards its command
  only to the active video tab, including while the YouTube iframe has focus.
  Both paths use the same Save action, AI default, note draft, and feedback.
  Typing fields, menus, dialogs, and hidden tabs ignore shortcut captures.
  The connected web page shows the extension's assigned shortcut, including
  remapping or no assignment. Focus refreshes that assignment. An older
  extension shows an update hint; Save remains available.
  Disconnects retry with bounded backoff and recover on focus or visibility
  changes. Acknowledgements release pending commands; neither side replays a
  capture after timeout, navigation, or reconnect.

## Key Behavior
- **Auth**: the JWT is stored in `localStorage`, validated on read, and sent by
  the fetch wrapper. `setToken` and `removeToken` sync the extension and emit an
  auth-change event that `useSignedIn` subscribes to. A `401` on an
  authenticated request triggers one session-expired notice and a redirect to
  `/login`.
- **Sign-in forms**: field errors are associated with their input and announced.
  Google sign-in shows Google's light rectangular button in both app themes.
  The control follows the form width and keeps a light color scheme. If the script
  fails or is unavailable after five seconds, Retry reloads it; email sign-in
  stays usable. The client initializes once, and listeners and timers are
  removed when the form unmounts. Link forms associate invalid links with their
  error text too.
- **Server state**: TanStack Query. Moment lists poll every 5 seconds while a
  moment is resolving, queued, or waiting for a transcript; the video polls
  while its `transcript_status` is `pending` or its `overview_status` is
  `queued`, and the transcript while it is `pending`. Every job ends in an
  explicit state, so polling always stops.
  Mutations invalidate moments, the library, and the profile (credit balance).
- The moment strip under the player marks each moment on a thin rail. Marks
  closer than 22px merge into one numbered marker that opens a menu of its
  moments; each row seeks. Single marks have a 14×24px target and a tooltip
  with the time and the AI line (or note, or quote). Each marker is one tab
  stop, and the rail regroups when its width changes (`groupMarks.ts`).
- Moment timestamps and timeline marks use the saved capture time. Playing a
  moment starts five seconds earlier (clamped at zero), including search and
  exported links; the transcript quote has its own context window.
- **Library**: one field searches titles and channels or previews a pasted
  YouTube video link. Views select All, With moments, or With chats; their
  counts follow the search. A themed menu offers six sorts. A paste card
  checks membership, preserves the link's time, and offers Add and open or
  Add to library. Existing videos open directly; failed checks claim no
  membership state, and failed saves retry the original action in place. Open
  and library citation Watch actions are links, so they support new tabs.
  In-video citations still seek the current player.
- **Resurfacing**: Home shows an older moment in a stable daily order. Another
  advances through the eligible moments and wraps to the first. Empty results
  hide the section; failures show a retry. Imported moments use an approximate
  date label.
- **Home and video rows**: the four recent videos show thumbnail durations.
  Library rows separate channel, moment count, chats, activity, and the latest
  moment text. Feed groups follow capture order, with moments in video-time
  order inside each group. Quote-only moments keep their text preview.
- **Moment actions**: note editors use Enter to save, Shift+Enter for a new
  line, and Escape to cancel, matching the extension. Deleting asks inline
  before making a request. Escape or
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
  retry (signed in), transcript unavailable, pending (transcript still loading), or
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
  moment. The save button is a 32px target that appears on hover or keyboard
  focus within the line on desktop and is always shown on touch screens; a
  saved line keeps its mark.
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
  and opens the workspace on the Ask tab, at the link's start time (`t`) when
  it has one.
- **Search links**: moment hits open Moments at the saved moment as an arrival;
  passage hits open Transcript. Playback requests made before player setup
  are queued and retain the existing lead-in and autoplay fallback.
- **Playback help**: when YouTube reports blocked autoplay, the Press Play
  help waits 500 ms and appears only if playback still has not started, so a
  brief report does not push the controls below the player down.
- **Command palette**: ⌘K / Ctrl+K searches, asks the library, opens a pasted
  YouTube link, or jumps to a page. The header search shows ⌘K on Apple
  devices and Ctrl K elsewhere.
- **PWA**: `public/manifest.webmanifest` with a share target; sharing a YouTube
  video to VidWiz saves and opens it.
- **API errors**: Fetch and SSE failures normalize to a shared error type. Safe
  handled `4xx` messages may be shown; `5xx` and malformed responses use curated
  copy and may include the backend `X-Request-ID`. Action failures use toasts;
  failed page or section loads render retry states, including credit packs,
  tokens, recent videos, library chat history, the Ask access check, and the
  share target. An empty result is shown as empty, not as a failure.
- **Toasts**: errors are announced as alerts, other toasts politely. A toast's
  countdown pauses while it is hovered or has focus, so its action can't
  expire mid-use.
- **API tokens**: Revoke asks inside the row first, naming the token; Escape or
  Cancel returns focus to Revoke, and the confirmation stays until a pending revoke
  settles. A failed copy says so.

## Development
- `pnpm dev` with `VITE_API_URL` pointing at an API (for example a local backend
  or a test deployment).
- `pnpm lint`, `pnpm test`, `pnpm build`.

## Public HTML and indexing

`pnpm build` builds the browser bundle, then a separate Vite SSR bundle used
only during the build. `scripts/build.mjs` renders `/`, `/support`, and
`/privacy` through `src/entry-server.tsx`. Each output contains the page's
content, title, description, canonical, social metadata, and an `index, follow`
robots directive. The sitemap lists those three public URLs. Builds make no
API requests and never render account data.

The renderer also writes an empty `app.html` shell and a rendered `404.html`,
both with `noindex, follow` and no canonical. `scripts/verify-build.mjs` checks
the finished HTML and sitemap as part of every build. `dist-ssr` is a build
intermediate; only `dist` is uploaded as static assets.

The browser hydrates roots marked `data-prerendered`. Authentication uses a
signed-out server snapshot, then restores the stored session after hydration,
so `/` still becomes Home for signed-in users. Theme, platform-specific
keyboard labels, and reduced-motion classes preserve the initial server
markup. Landing content remains visible without JavaScript; reveal animations
start after mounting.

`Seo` owns public metadata. Its generated tags carry Helmet's ownership marker
so client navigation replaces them instead of adding duplicates. The app-level
fallback and account pages use `noindex, follow`; page titles can override the
fallback title. The pinned Helmet fork has a small pnpm patch in
`patches/helmet-strict-mode.patch`: its dispatcher re-registers on React Strict
Mode's development remount. Hydration tests cover metadata retention and
navigation with Strict Mode enabled.

### Cloudflare routing

`src/worker.ts` selects the built HTML through the `ASSETS` binding in
`wrangler.jsonc`. It does not render React or contact the backend at runtime.

- `/`, `/support`, and `/privacy` serve their public HTML. Trailing-slash and
  `.html` variants redirect permanently to the canonical path.
- Login, signup, library, search, Ask, settings, share, and `/v/:videoId` serve
  the client-only shell with an `X-Robots-Tag: noindex, follow` header. Query
  parameters remain in the browser URL for React to use.
- Legacy routes redirect permanently, preserving query parameters. Old
  `/wiz/:videoId` links select the Ask tab.
- Unknown paths return the rendered not-found page with HTTP 404. React also
  shows it for unknown paths reached through client navigation. Direct requests
  for `/app.html` and `/404.html` return 404.
- Static assets retain their normal responses. The asset, landing-recording,
  and brand directories bypass the Worker. HTML requests support GET and HEAD.

The blanket SPA fallback is disabled. Deploy `wrangler.jsonc`, the Worker,
and the generated assets together through the existing frontend workflow.
`pnpm dev` remains Vite's development server; it does not emulate production
HTTP status codes or redirects. The SSR, hydration, and Worker tests run with
`pnpm test`.

## Tab titles
Tab titles name what is open, most specific first, joined with ` · ` and
ending in `VidWiz`. `documentTitle` in `src/lib/title.ts` builds them; public
pages pass the result to `Seo`, and signed-in pages use `PageTitle`.
- The landing page uses `LANDING_TITLE`, including in the generated HTML.
- A video page adds its open panel, as in `<video title> · Ask · VidWiz`.
  While the video loads, fails, or has no title yet, the title is
  `Video · VidWiz`; it never shows the video ID.
- A library chat is named by its first question, shortened, and keeps that
  name through follow-ups. A new chat is `Ask your library · VidWiz`.
- Search uses `"<query>" · Search · VidWiz` with curly quotes.

Chat controls are called **New chat** and **Chat history** everywhere.
Library Ask lists its chats in a sidebar on wide screens. Below 1024px the
same chats open from a Chat history menu in the chat header, the component
video Ask uses (`features/chat/ChatHistoryMenu.tsx`). The open chat is marked
with `aria-current` in both. On phones the "Ask your library" title is
visually hidden to fit both controls; it stays the page heading for screen
readers.

Every scrolling area uses the slim, theme-colored scrollbar defined in
`src/index.css`. A component can still hide it with a utility, as the tab strip
does.

## UI Screenshot Workflow
`scripts/screenshot_pages.py` captures the 2.x pages and still needs updating
for the v3 routes and states.

## Brand assets

Navigation, landing, and authentication pages use the primary SVG mark.
`index.html` declares the favicon and Apple icon; the manifest keeps standard
and maskable icons separate. The default social card is shared by Open Graph
and Twitter metadata, including page-specific titles from `Seo`.
See [Brand assets](branding.md) for the files, font provenance, and regeneration.
