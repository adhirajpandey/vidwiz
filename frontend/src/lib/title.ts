/** Tab titles name what is open, most specific first, then the product. */
export const SITE_NAME = 'VidWiz';
/** The landing page's title; `index.html` repeats it so startup shows no change. */
export const LANDING_TITLE = `${SITE_NAME} · Keep the moments worth coming back to`;

export function documentTitle(...parts: string[]): string {
  return [...parts, SITE_NAME].join(' · ');
}

/** One line of `text`, cut at a word boundary when it is longer than `max`. */
export function shortTitle(text: string, max = 60): string {
  const line = text.split(/\s+/).filter(Boolean).join(' ');
  if (line.length <= max) return line;
  const cut = line.slice(0, max);
  const space = cut.lastIndexOf(' ');
  return `${(space > 0 ? cut.slice(0, space) : cut).replace(/[\s.,;:!?-]+$/, '')}…`;
}
