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

/** Converts an `H:MM:SS` or `M:SS` note timestamp to seconds. */
export function timestampToSeconds(timestamp: string): number {
  return timestamp.split(':').reduce((seconds, part) => seconds * 60 + Number(part), 0);
}
