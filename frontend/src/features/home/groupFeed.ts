import type { FeedMoment } from '../../api';
import { dayLabel } from '../../lib/format';

export interface FeedGroup {
  key: string;
  day: string;
  videoId: string | null;
  title: string | null;
  moments: FeedMoment[];
}

/** One group per video and local day, newest group first and playback order within it. */
export function groupFeed(moments: FeedMoment[]): FeedGroup[] {
  const groups: FeedGroup[] = [];
  for (const moment of moments) {
    const day = dayLabel(moment.created_at);
    const last = groups.find(group => group.day === day && group.videoId === moment.video_id);
    if (last && last.day === day && last.videoId === moment.video_id && moment.video_id) {
      last.moments.push(moment);
    } else {
      groups.push({ key: `${moment.id}`, day, videoId: moment.video_id, title: moment.video_title, moments: [moment] });
    }
  }
  for (const group of groups) group.moments.sort((a, b) => a.at_seconds - b.at_seconds || a.id - b.id);
  return groups;
}
