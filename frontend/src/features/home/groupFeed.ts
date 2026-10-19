import type { FeedMoment } from '../../api';
import { dayLabel } from '../../lib/format';

export interface FeedGroup {
  key: string;
  day: string;
  videoId: string | null;
  title: string | null;
  moments: FeedMoment[];
}

/** Consecutive moments from the same video and day share one heading. */
export function groupFeed(moments: FeedMoment[]): FeedGroup[] {
  const groups: FeedGroup[] = [];
  for (const moment of moments) {
    const day = dayLabel(moment.created_at);
    const last = groups.at(-1);
    if (last && last.day === day && last.videoId === moment.video_id && moment.video_id) {
      last.moments.push(moment);
    } else {
      groups.push({ key: `${moment.id}`, day, videoId: moment.video_id, title: moment.video_title, moments: [moment] });
    }
  }
  return groups;
}
