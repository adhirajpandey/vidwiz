import { StrictMode } from 'react';
import { createRoot, hydrateRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import './index.css';
import AppContent from './app/AppContent';
import { syncExtensionAuth } from './lib/authUtils';

// Keep the extension's token in step with the web session.
syncExtensionAuth();

const app = (
  <StrictMode>
    <HelmetProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </HelmetProvider>
  </StrictMode>
);
const root = document.getElementById('root')!;
if (root.dataset.prerendered === 'true') {
  hydrateRoot(root, app);
} else {
  createRoot(root).render(app);
}
