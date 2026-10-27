/** Cloudflare serves built HTML; React and API requests still run in the browser. */
type Env = { ASSETS: { fetch(request: Request): Promise<Response> } };

const PUBLIC_PAGES: Record<string, string> = {
  '/': '/index.html',
  '/support': '/support.html',
  '/privacy': '/privacy.html',
};
const APP_ROUTE = /^\/(?:login|signup|library|search|ask|settings|share|v\/[^/]+)$/i;
const LEGACY_ROUTES: Record<string, string> = {
  '/dashboard': '/library', '/wiz': '/', '/profile': '/settings', '/help': '/settings#tokens',
};

function redirect(url: URL, path: string): Response {
  const target = new URL(path, url);
  const query = new URLSearchParams(url.search);
  // Explicit redirect parameters (the old Wiz route's Ask tab) take precedence.
  target.searchParams.forEach((value, key) => query.set(key, value));
  target.search = query.toString();
  return Response.redirect(target.href, 301);
}

async function html(request: Request, env: Env, file: string, status = 200, noIndex = false) {
  const assetUrl = new URL(request.url);
  assetUrl.pathname = file;
  assetUrl.search = '';
  // Conditional/range headers for a different URL must not turn the shell into a 304/206.
  const asset = await env.ASSETS.fetch(new Request(assetUrl, { method: 'GET' }));
  if (!asset.ok) return new Response('Page unavailable', { status: 503 });
  const headers = new Headers(asset.headers);
  headers.set('Content-Type', 'text/html; charset=utf-8');
  headers.set('Cache-Control', 'no-cache');
  if (noIndex) headers.set('X-Robots-Tag', 'noindex, follow');
  return new Response(request.method === 'HEAD' ? null : asset.body, { status, headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    const url = new URL(request.url);
    const path = url.pathname;
    const normalized = path.replace(/\/+$/, '') || '/';
    const publicPath = normalized.toLowerCase().replace(/\.html$/, '').replace(/^\/index$/, '/');
    if (PUBLIC_PAGES[publicPath]) {
      if (path !== publicPath) return redirect(url, publicPath);
      return html(request, env, PUBLIC_PAGES[publicPath]);
    }
    const legacy = LEGACY_ROUTES[normalized.toLowerCase()];
    if (legacy) return redirect(url, legacy);
    const oldVideo = normalized.match(/^\/(dashboard|wiz)\/([^/]+)$/i);
    if (oldVideo) return redirect(url, `/v/${oldVideo[2]}${oldVideo[1].toLowerCase() === 'wiz' ? '?tab=ask' : ''}`);
    if (APP_ROUTE.test(normalized)) {
      if (path !== normalized) return redirect(url, normalized);
      return html(request, env, '/app.html', 200, true);
    }
    // The application shell is an implementation asset, not another indexable page.
    if (path !== '/app.html' && path !== '/404.html') {
      const asset = await env.ASSETS.fetch(request);
      if (asset.status !== 404) return asset;
    }
    return html(request, env, '/404.html', 404, true);
  },
};
