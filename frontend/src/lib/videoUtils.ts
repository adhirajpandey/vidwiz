const VIDEO_ID_PATTERN = /^[a-zA-Z0-9_-]{11}$/;
const PATH_PREFIXES = ['/shorts/', '/live/', '/embed/'];

/**
 * Extracts a YouTube video ID from various URL formats or raw ID.
 * Returns null if invalid or if it's a playlist URL.
 */
export function extractVideoId(input: string): string | null {
  const trimmed = input?.trim();
  if (!trimmed || trimmed.includes('list=')) return null;
  if (VIDEO_ID_PATTERN.test(trimmed)) return trimmed;

  // Repair router artifacts such as `https:/youtu.be/...`, and add a missing protocol.
  let urlToParse = trimmed;
  if (/^https?:\/[^/]/.test(urlToParse)) {
    urlToParse = urlToParse.replace(/^(https?):\/+/, '$1://');
  } else if (!urlToParse.startsWith('http')) {
    urlToParse = `https://${urlToParse}`;
  }

  let url: URL;
  try {
    url = new URL(urlToParse);
  } catch {
    return null;
  }

  const hostname = url.hostname.replace('www.', '');
  let candidate: string | null | undefined;
  if (hostname === 'youtu.be') {
    candidate = url.pathname.slice(1);
  } else if (hostname.includes('youtube.com')) {
    const prefix = PATH_PREFIXES.find((p) => url.pathname.startsWith(p));
    if (url.pathname === '/watch') candidate = url.searchParams.get('v');
    else if (prefix) candidate = url.pathname.slice(prefix.length);
  }
  return candidate && VIDEO_ID_PATTERN.test(candidate) ? candidate : null;
}

/**
 * The start time a YouTube link asks for, in seconds: `t` or `start` in the query
 * or `#t=` in the hash, as plain seconds or `1h2m3s`. Returns 0 when there is none.
 */
export function extractStartSeconds(input: string): number {
  const trimmed = input?.trim();
  if (!trimmed) return 0;
  let url: URL;
  try {
    url = new URL(/^https?:\/\//.test(trimmed) ? trimmed : `https://${trimmed}`);
  } catch {
    return 0;
  }
  const raw = url.searchParams.get('t') ?? url.searchParams.get('start') ?? url.hash.match(/[#&]t=([^&]+)/)?.[1];
  if (!raw) return 0;
  if (/^\d+$/.test(raw)) return Number(raw);
  const match = raw.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/);
  if (!match) return 0;
  return Number(match[1] ?? 0) * 3600 + Number(match[2] ?? 0) * 60 + Number(match[3] ?? 0);
}

export function isValidVideoId(value: string): boolean {
  return VIDEO_ID_PATTERN.test(value);
}
