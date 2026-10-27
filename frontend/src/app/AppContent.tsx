import { QueryClientProvider } from '@tanstack/react-query';
import App from '../App';
import { queryClient } from './queryClient';
import ToastProvider from '../components/ToastProvider';
import { TooltipProvider } from '../components/ui/Tooltip';
import ScrollToTop from '../components/ScrollToTop';
import SessionExpiredHandler from '../components/SessionExpiredHandler';
import ErrorBoundary from '../components/ErrorBoundary';

/** The same provider tree is used for build-time rendering and browser hydration. */
export default function AppContent() {
  return (
    <QueryClientProvider client={queryClient}>
      <ScrollToTop />
      <ToastProvider>
        <TooltipProvider>
          <ErrorBoundary>
            <SessionExpiredHandler />
            <App />
          </ErrorBoundary>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
