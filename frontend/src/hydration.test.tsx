// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, waitFor } from '@testing-library/react';
import { hydrateRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import AppContent from './app/AppContent';
import { renderPage } from './entry-server';

// Keep account data out of the hydration test; auth and routing remain real.
vi.mock('./features/home/HomePage', () => ({ default: () => <h1>Your saved moments</h1> }));
vi.mock('./hooks/useProfile', () => ({ useProfile: () => ({ data: { name: 'Test', credits_balance: 100 } }) }));
vi.mock('./app/CommandPalette', () => ({ default: () => null }));

let root: Root | undefined;
beforeEach(() => {
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  document.body.replaceChildren();
  document.head.replaceChildren();
  document.documentElement.className = '';
  localStorage.clear();
  HelmetProvider.canUseDOM = true;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function hydrate(path: string) {
  window.history.replaceState({}, '', path);
  // Simulate the Node renderer; useSyncExternalStore still uses its server snapshots.
  HelmetProvider.canUseDOM = false;
  const { head, body } = renderPage(path);
  HelmetProvider.canUseDOM = true;
  document.head.innerHTML = head;
  document.body.innerHTML = `<div id="root">${body}</div>`;
  // jsdom does not initialize the media muted property from its HTML attribute.
  document.querySelectorAll<HTMLVideoElement>('video[muted]').forEach(video => { video.muted = true; });
  const errors = vi.fn();
  await act(async () => {
    root = hydrateRoot(document.getElementById('root')!, (
      <StrictMode>
        <HelmetProvider>
          <BrowserRouter><AppContent /></BrowserRouter>
        </HelmetProvider>
      </StrictMode>
    ), { onRecoverableError: errors });
  });
  return errors;
}

it.each(['/', '/support', '/privacy', '/missing-page'])('hydrates %s without mismatches for a dark-theme Mac visitor', async path => {
  localStorage.setItem('theme', 'dark');
  Object.defineProperty(navigator, 'platform', { value: 'MacIntel', configurable: true });
  const consoleError = vi.spyOn(console, 'error');
  const errors = await hydrate(path);
  await waitFor(() => expect(document.querySelectorAll('h1')).toHaveLength(1));
  expect(errors).not.toHaveBeenCalled();
  expect(consoleError).not.toHaveBeenCalled();
  expect(document.querySelectorAll('meta[name="robots"]')).toHaveLength(1);
  if (path !== '/missing-page') expect(document.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
  if (path === '/') expect(document.body.textContent).toContain('⌥');
  else expect(document.documentElement.classList.contains('dark')).toBe(true);
});

it('hydrates the public homepage before restoring the signed-in home', async () => {
  const payload = btoa(JSON.stringify({ user_id: 1, exp: Math.floor(Date.now() / 1000) + 3600 }));
  localStorage.setItem('token', `header.${payload}.signature`);
  const errors = await hydrate('/');
  await waitFor(() => expect(document.querySelector('h1')?.textContent).toBe('Your saved moments'));
  expect(errors).not.toHaveBeenCalled();
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, follow');
  expect(document.querySelector('link[rel="canonical"]')).toBeNull();
  expect(document.documentElement.classList.contains('landing-page')).toBe(false);
});

it('replaces public metadata when navigating to login, then restores it on return', async () => {
  await hydrate('/support');
  await act(async () => {
    document.querySelector<HTMLAnchorElement>('a[href="/login"]')!.click();
  });
  await waitFor(() => expect(window.location.pathname).toBe('/login'));
  // The URL changes before the lazy route module has mounted its metadata.
  await waitFor(() => expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://vidwiz.online/login'));
  expect(document.querySelectorAll('meta[name="robots"]')).toHaveLength(1);
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, follow');
  expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://vidwiz.online/login');
  await act(async () => {
    window.history.pushState({}, '', '/privacy');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await waitFor(() => expect(document.title).toBe('Privacy policy · VidWiz'));
  expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('index, follow');
  expect(document.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
  expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://vidwiz.online/privacy');
});
