import workerConfig from '../../wrangler.jsonc?raw';
import { expect, it, vi } from 'vitest';
import worker from './worker';

function assets() {
  return { ASSETS: { fetch: vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (['/index.html', '/support.html', '/privacy.html', '/app.html', '/404.html'].includes(path)) {
      return new Response(`<html>${path}</html>`, { headers: { 'Content-Type': 'text/html' } });
    }
    if (path === '/robots.txt') return new Response('User-agent: *\nAllow: /');
    return new Response('Missing asset', { status: 404 });
  }) } };
}

it.each(['/', '/support', '/privacy'])('serves public HTML at %s without a noindex header', async path => {
  const env = assets();
  const response = await worker.fetch(new Request(`https://vidwiz.online${path}?utm_source=test`), env);
  expect(response.status).toBe(200);
  expect(response.headers.has('X-Robots-Tag')).toBe(false);
  expect(await response.text()).toContain(path === '/' ? '/index.html' : `${path}.html`);
});

it.each(['/login', '/signup', '/library', '/search?q=notes', '/ask?c=2', '/settings', '/share?url=test', '/v/abc123?t=45&tab=ask'])('preserves app deep link %s with a noindex shell', async path => {
  const response = await worker.fetch(new Request(`https://vidwiz.online${path}`), assets());
  expect(response.status).toBe(200);
  expect(response.headers.get('X-Robots-Tag')).toBe('noindex, follow');
  expect(await response.text()).toContain('/app.html');
});

it.each(['/does-not-exist', '/v/abc/extra', '/app.html', '/404.html'])('returns a useful 404 for %s', async path => {
  const response = await worker.fetch(new Request(`https://vidwiz.online${path}`), assets());
  expect(response.status).toBe(404);
  expect(response.headers.get('X-Robots-Tag')).toBe('noindex, follow');
  expect(await response.text()).toContain('/404.html');
});

it.each([
  ['/support/?from=test', '/support?from=test'],
  ['/support.html', '/support'],
  ['/index.html', '/'],
  ['/privacy/', '/privacy'],
  ['/dashboard', '/library'],
  ['/dashboard/abc?t=10', '/v/abc?t=10'],
  ['/wiz/abc?t=20&tab=overview', '/v/abc?t=20&tab=ask'],
  ['/profile', '/settings'],
  ['/help', '/settings#tokens'],
])('redirects %s permanently to %s', async (from, to) => {
  const response = await worker.fetch(new Request(`https://vidwiz.online${from}`), assets());
  expect(response.status).toBe(301);
  expect(response.headers.get('Location')).toBe(`https://vidwiz.online${to}`);
});

it('serves static files, supports HEAD, and rejects writes without returning app HTML', async () => {
  const env = assets();
  expect(await (await worker.fetch(new Request('https://vidwiz.online/robots.txt'), env)).text()).toContain('User-agent');
  const head = await worker.fetch(new Request('https://vidwiz.online/support', { method: 'HEAD' }), env);
  expect(head.status).toBe(200);
  expect(await head.text()).toBe('');
  expect((await worker.fetch(new Request('https://vidwiz.online/share', { method: 'POST' }), env)).status).toBe(405);
});

it('reports a missing build asset as a server failure, not a successful empty page', async () => {
  const response = await worker.fetch(new Request('https://vidwiz.online/support'), {
    ASSETS: { fetch: async () => new Response(null, { status: 404 }) },
  });
  expect(response.status).toBe(503);
});

it('configures explicit routing rather than the blanket SPA fallback', () => {
  const config = JSON.parse(workerConfig);
  expect(config.main).toBe('frontend/src/worker.ts');
  expect(config.assets.binding).toBe('ASSETS');
  expect(config.assets.html_handling).toBe('none');
  expect(config.assets.not_found_handling).toBe('none');
  expect(config.assets.run_worker_first).toContain('/*');
});
