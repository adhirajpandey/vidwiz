import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import App from './App.tsx';
import { queryClient } from './app/queryClient';
import ToastProvider from './components/ToastProvider';
import { TooltipProvider } from './components/ui/Tooltip';
import ScrollToTop from './components/ScrollToTop';
import SessionExpiredHandler from './components/SessionExpiredHandler';
import ErrorBoundary from './components/ErrorBoundary';
import { syncExtensionAuth } from './lib/authUtils';

// Keep the extension's token in step with the web session.
syncExtensionAuth();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScrollToTop />
          <ToastProvider>
            <TooltipProvider>
              <ErrorBoundary>
                <SessionExpiredHandler />
                <App />
              </ErrorBoundary>
            </TooltipProvider>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </HelmetProvider>
  </StrictMode>,
);
