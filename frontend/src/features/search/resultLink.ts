import type { SearchResult } from '../../api';

export function resultLink(result: SearchResult): string {
  const base = `/v/${result.video.video_id}?t=${Math.floor(result.start_seconds)}`;
  return result.kind === 'moment' ? `${base}&m=${result.moment.id}` : base;
}
