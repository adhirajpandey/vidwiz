import { expect, it } from 'vitest';
import type { FeedMoment } from '../../api';
import { groupFeed } from './groupFeed';

it('merges interleaved videos per day and sorts moments by video time without changing input', () => {
  const row = (id: number, video_id: string | null, at_seconds: number, created_at = '2026-10-24T12:00:00Z') => ({ id, video_id, at_seconds, created_at }) as FeedMoment;
  const rows = [row(1, 'a', 90), row(2, 'b', 10), row(3, 'a', 20), row(4, null, 10), row(5, null, 5), row(6, 'a', 30, '2026-10-23T12:00:00Z')];
  expect(groupFeed(rows).map(g => g.moments.map(m => m.id))).toEqual([[3, 1], [2], [4], [5], [6]]);
  expect(rows.map(m => m.id)).toEqual([1, 2, 3, 4, 5, 6]);
});
