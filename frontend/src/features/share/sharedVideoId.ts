import { extractVideoId } from '../../lib/videoUtils';

/** The first YouTube video found in what another app shared. */
export function sharedVideoId(params: URLSearchParams): string | null {
  for (const key of ['url', 'text', 'title']) {
    const value = params.get(key);
    if (!value) continue;
    for (const word of value.split(/\s+/)) {
      const id = extractVideoId(word);
      if (id) return id;
    }
  }
  return null;
}
