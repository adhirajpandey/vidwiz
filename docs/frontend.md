# VidWiz Frontend

## Purpose
Describe the web app's structure, responsibilities, and how it integrates with the backend. This is a high-level guide for engineers and coding agents.

## Scope
- React app structure, routing, and page responsibilities.
- API integration and auth handling.
- The Wiz chat flow and video status streaming.

## Components
### App Shell
- **Entry**: `src/main.tsx` mounts React, sets up `BrowserRouter`, `ToastProvider`, and `ScrollToTop`.
- **Routing**: `src/App.tsx` defines all routes and wraps them with `Layout`.
- **Layout**: `components/layout/Layout.tsx` provides navbar + footer on non-landing pages.
- **Navbar**: `components/layout/Navbar.tsx` handles navigation, theme toggle, and auth state display.

### Pages (Routes)
- **Landing** (`/`): Marketing content and CTAs (`pages/LandingPage.tsx`).
- **Login** (`/login`): Email/password and Google sign-in (`pages/LoginPage.tsx`).
- **Signup** (`/signup`): Registration + Google sign-up (`pages/SignupPage.tsx`).
- **Dashboard** (`/dashboard`): Search + list videos for current user (`pages/DashboardPage.tsx`).
- **Video** (`/dashboard/:videoId`): Video details, AI summary, and notes list (`pages/VideoPage.tsx`).
- **Profile** (`/profile`): User profile, AI notes toggle, and long-term token management (`pages/ProfilePage.tsx`).
- **Wiz Entry** (`/wiz`): Input for YouTube URL/ID (`pages/WizEntryPage.tsx`).
- **Wiz Workspace** (`/wiz/*`): Chat + video player + metadata + summary (`pages/WizWorkspacePage.tsx`).

### Shared UI
- **Cards/UX**: `components/VideoCard.tsx`, `components/NoteCard.tsx`, `components/ui/GlassCard.tsx`.
- **Toasts**: `hooks/useToast.tsx` and `components/ui/Toast.tsx`.
- **Auth layout**: `components/auth/AuthLayout.tsx`.
- **Modals**: `GuestLimitModal`, `RegisteredLimitModal` for Wiz rate-limit handling.

### Utilities
- **Auth utilities**: `lib/authUtils.ts` (JWT storage, decode, expiry checks, headers).
- **Video parsing**: `lib/videoUtils.ts` (extracts YouTube video IDs).
- **API**: `api/*` (axios client + domain-specific API wrappers).

## Key Flows
### 1) Auth & Session
- Login/signup uses `authApi` (email/password or Google OAuth).
- JWT is stored in `localStorage` and injected into requests by `api/client.ts`.
- Protected routes use `ProtectedRoute` and `isAuthenticated()`.

### 2) Dashboard Video Search
- `DashboardPage` calls `videosApi.listVideos` with search + pagination.
- Results render via `VideoCard` and link to `/dashboard/:videoId`.

### 3) Video Detail + Notes
- `VideoPage` fetches video details (`videosApi.getVideo`).
- Notes are listed via `notesApi.listNotes` and displayed with `NoteCard`.
- Notes can be edited or deleted in the UI; note creation is not currently exposed in the web UI.

### 4) Wiz Chat (Conversation)
- `WizEntryPage` validates YouTube URL/ID and navigates to `/wiz/:videoId`.
- `WizWorkspacePage`:
  - Creates a conversation (`conversationsApi.createConversation`).
  - Streams video readiness from `/videos/:id/stream` (SSE over `fetch`).
  - Streams chat responses via `/conversations/:id/messages` (SSE-style streaming).
  - Handles guest and registered rate limits via modals.

### 5) Guest Sessions
- If no token, a `guestSessionId` is generated in `sessionStorage`.
- Guest ID is sent via `X-Guest-Session-ID` header for chat and video status streams.

## Interfaces / Integration Points
- **Backend API**: All requests are made to `config.API_URL` (currently `/v2`).
- **Auth headers**: Injected by axios interceptor; some streaming calls use `getAuthHeaders()`.
- **Google OAuth**: `GoogleSignInButton` uses Google Identity Services with `GOOGLE_CLIENT_ID`.
- **YouTube**: Links open `youtube.com/watch?v=...` and embeds use `youtube.com/embed/...`.

## Data / State (High-Level)
- **Auth state**: JWT in `localStorage`, decoded for display.
- **Guest state**: `guestSessionId` in `sessionStorage` for unauthenticated chat.
- **UI state**: Page-local `useState` for forms, loading, and modals.
- **Video state**: `VideoRead` from backend drives metadata and summary.
- **Conversation state**: In-memory message list in `WizWorkspacePage`.

## Operational Notes
- Theme is toggled by adding/removing the `dark` class on `documentElement`.
- Tailwind CSS tokens are defined via CSS variables in `index.css`.
- API base URL is hard-coded in `src/config.ts` for both dev/prod (no `.env` usage in frontend).

## Open Questions
- Should the web app expose note creation (not just edit/delete)?
- Do we need a unified auth flow for guest upgrade inside the Wiz modals?
- Should API base URL and Google client ID move to environment variables?

## Interaction Overview (ASCII)
```
Browser
  |
  v
React App (Router + Layout)
  |
  +--> Auth Pages (Login/Signup)
  |       |
  |       v
  |    authApi -> /v2/auth/*
  |
  +--> Dashboard/Video
  |       |
  |       v
  |    videosApi/notesApi -> /v2/videos, /v2/notes
  |
  +--> Wiz Entry/Workspace
          |
          +--> video status stream -> /v2/videos/:id/stream
          +--> conversations -> /v2/conversations
          +--> guest session id -> X-Guest-Session-ID
```
