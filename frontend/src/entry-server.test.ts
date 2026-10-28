import { afterEach, expect, it, vi } from 'vitest';
import { renderPage } from './entry-server';

afterEach(() => vi.unstubAllGlobals());

it.each([
  ['/', 'YouTube Notes with Timestamps & AI Chat | VidWiz', 'Take timestamped notes on YouTube'],
  ['/support', 'Help · VidWiz', 'Connect your account'],
  ['/privacy', 'Privacy policy · VidWiz', 'What VidWiz handles'],
])('renders %s with content and one consistent set of metadata, without a browser or API', (path, title, text) => {
  const fetch = vi.fn(() => { throw new Error('Prerender must not call the API'); });
  vi.stubGlobal('fetch', fetch);
  const { head, body } = renderPage(path);
  expect(body).toContain(text);
  expect(body.match(/<h1[ >]/g)).toHaveLength(1);
  expect(head.match(/<title[ >]/g)).toHaveLength(1);
  expect(head).toContain(title.replaceAll('&', '&amp;'));
  expect(head.match(/rel="canonical"/g)).toHaveLength(1);
  expect(head).toContain(`href="https://vidwiz.online${path}"`);
  expect(head.match(/name="robots"/g)).toHaveLength(1);
  expect(head).toContain('content="index, follow"');
  expect(head.match(/name="description"/g)).toHaveLength(1);
  expect(head).toContain('property="og:title"');
  expect(head).toContain('name="twitter:title"');
  expect(fetch).not.toHaveBeenCalled();
});

it('does not give the client-only shell or not-found page a homepage canonical', () => {
  for (const path of [null, '/404']) {
    const { head, body } = renderPage(path);
    expect(head).toContain('noindex, follow');
    expect(head).not.toContain('rel="canonical"');
    if (path === null) expect(body).toBe('');
    else expect(body).toContain('Page not found');
  }
});
