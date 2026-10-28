import { StrictMode } from 'react';
import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import type { HelmetServerState } from 'react-helmet-async';
import AppContent from './app/AppContent';
import Seo from './components/Seo';

/** Render only public pages (or the empty, noindex application shell), without API requests. */
export function renderPage(path: string | null) {
  const context = {} as { helmet: HelmetServerState };
  const body = renderToString(
    <StrictMode>
      <HelmetProvider context={context}>
        {path === null ? (
          <Seo title="VidWiz" description="Save and search YouTube moments, and ask questions across your library." noIndex />
        ) : (
          <StaticRouter location={path}>
            <AppContent />
          </StaticRouter>
        )}
      </HelmetProvider>
    </StrictMode>,
  );
  const { helmet } = context;
  return { body, head: helmet.title.toString() + helmet.meta.toString() + helmet.link.toString() };
}
