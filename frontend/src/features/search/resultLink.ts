import type { SearchResult } from '../../api';
import { playFrom } from '../moments/queries';

export function resultLink(result: SearchResult): string {
  const seconds = result.kind === 'moment' ? playFrom(result.moment) : result.start_seconds;
  const base = `/v/${result.video.video_id}?t=${Math.floor(seconds)}`;
  return result.kind === 'moment' ? `${base}&m=${result.moment.id}&tab=moments` : `${base}&tab=transcript`;
}
