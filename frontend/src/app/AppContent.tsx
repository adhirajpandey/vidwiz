import { lazy, Suspense } from 'react';
import type { ComponentType } from 'react';
import { useLocation } from 'react-router-dom';
import LandingPage from '../features/landing/LandingPage';
import { useSignedIn } from '../hooks/useSignedIn';
import ToastProvider from '../components/ToastProvider';
import ScrollToTop from '../components/ScrollToTop';
import SessionExpiredHandler from '../components/SessionExpiredHandler';
import ErrorBoundary from '../components/ErrorBoundary';

const LazyApplication = lazy(() => import('./Application'));
const LazyPublicPages = lazy(() => import('./PublicPages'));
const PUBLIC_PAGES = new Set(['/support', '/privacy', '/404']);

// The server supplies eager components so public pages render synchronously.
// The browser loads those modules only when their routes need them.
export default function AppContent({ application: Application = LazyApplication, publicPages: PublicPages = LazyPublicPages }: {
  application?: ComponentType;
  publicPages?: ComponentType;
}) {
  const signedIn = useSignedIn();
  const { pathname } = useLocation();
  return (
    <>
      <ScrollToTop />
      <ToastProvider>
        <ErrorBoundary>
          <SessionExpiredHandler />
          <Suspense fallback={<div role="status" aria-label="Loading" className="flex justify-center py-16"><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent text-muted-foreground" /></div>}>
            {!signedIn && pathname === '/' ? <LandingPage /> : !signedIn && PUBLIC_PAGES.has(pathname) ? <PublicPages /> : <Application />}
          </Suspense>
        </ErrorBoundary>
      </ToastProvider>
    </>
  );
}
