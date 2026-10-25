/** The Library field treats words as searches, even when they have 11 characters. */
export function looksLikeLink(text: string): boolean {
  return /^(https?:\/\/)?([\w-]+\.)*(youtube\.com|youtu\.be)\//i.test(text.trim());
}

/** YouTube accepts seconds and h/m/s durations in t, start, or a timestamp hash. */
export function linkTime(text: string): number | null {
  try {
    const url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
    const value = url.searchParams.get('t') ?? url.searchParams.get('start') ?? new URLSearchParams(url.hash.slice(1)).get('t');
    if (!value) return null;
    if (/^\d+(?:\.\d+)?$/.test(value)) return Math.floor(Number(value));
    const match = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(value);
    return match && match[0] ? Number(match[1] ?? 0) * 3600 + Number(match[2] ?? 0) * 60 + Number(match[3] ?? 0) : null;
  } catch { return null; }
}
