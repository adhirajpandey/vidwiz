// Vite fingerprints these URLs in both the client and prerendered HTML.
const assets = import.meta.glob<string>('../../assets/landing/*', { eager: true, query: '?url', import: 'default' });
export function mediaUrl(name: string, extension: 'mp4' | 'webp') {
  const url = assets[`../../assets/landing/${name}.${extension}`];
  if (!url) throw new Error(`Missing landing recording: ${name}.${extension}`);
  return url;
}

// Match landing.css, including at the 760px boundary.
export const MOBILE_MEDIA = '(max-width: 760px)';
export const DESKTOP_MEDIA = '(min-width: 760.01px)';
export const EMPTY_POSTER = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
