import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import AppShell from './app/AppShell';
import { useSignedIn } from './hooks/useSignedIn';
const LoginPage = lazy(() => import('./features/auth/LoginPage'));
const SignupPage = lazy(() => import('./features/auth/SignupPage'));
const HomePage = lazy(() => import('./features/home/HomePage'));
import LandingPage from './features/landing/LandingPage';
const LibraryPage = lazy(() => import('./features/library/LibraryPage'));
const SearchPage = lazy(() => import('./features/search/SearchPage'));
const SettingsPage = lazy(() => import('./features/settings/SettingsPage'));
const SharePage = lazy(() => import('./features/share/SharePage'));
import PrivacyPolicyPage from './features/landing/PrivacyPolicyPage';
import SupportPage from './features/landing/SupportPage';
import Seo from './components/Seo';
import NotFoundPage from './features/landing/NotFoundPage';
import Spinner from './components/ui/Spinner';

// Account and workspace pages load only when their route is opened.
const VideoPage = lazy(() => import('./features/video/VideoPage'));
const AskPage = lazy(() => import('./features/ask/AskPage'));

function RequireAuth({ children }: { children: ReactNode }) {
  const signedIn = useSignedIn();
  const location = useLocation();
  if (signedIn) return children;
  return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
}

function SignedOutOnly({ children }: { children: ReactNode }) {
  return useSignedIn() ? <Navigate to="/" replace /> : children;
}

/** Links from the 2.x app and extension keep working. */
function LegacyVideo({ tab }: { tab?: string }) {
  const { videoId = '' } = useParams();
  return <Navigate to={`/v/${videoId}${tab ? `?tab=${tab}` : ''}`} replace />;
}

export default function App() {
  const signedIn = useSignedIn();
  return (
    <AppShell>
      <Seo title="VidWiz" description="Save and search YouTube moments, and ask questions across your library." noIndex />
      <Suspense fallback={<div className="flex justify-center py-16"><Spinner /></div>}>
      <Routes>
        <Route path="/" element={signedIn ? <HomePage /> : <LandingPage />} />
        <Route path="/login" element={<SignedOutOnly><LoginPage /></SignedOutOnly>} />
        <Route path="/signup" element={<SignedOutOnly><SignupPage /></SignedOutOnly>} />
        <Route path="/v/:videoId" element={<VideoPage />} />
        <Route path="/library" element={<RequireAuth><LibraryPage /></RequireAuth>} />
        <Route path="/search" element={<RequireAuth><SearchPage /></RequireAuth>} />
        <Route path="/ask" element={<RequireAuth><AskPage /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
        <Route path="/share" element={<SharePage />} />
        <Route path="/privacy" element={<PrivacyPolicyPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/dashboard" element={<Navigate to="/library" replace />} />
        <Route path="/dashboard/:videoId" element={<LegacyVideo />} />
        <Route path="/wiz/:videoId" element={<LegacyVideo tab="ask" />} />
        <Route path="/wiz" element={<Navigate to="/" replace />} />
        <Route path="/profile" element={<Navigate to="/settings" replace />} />
        <Route path="/help" element={<Navigate to="/settings#tokens" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </Suspense>
    </AppShell>
  );
}
