import { describe, expect, it } from 'vitest';
import type { VideoRead } from '../../api';
import { videoHasPendingWork } from './status';

const video = (fields: Partial<VideoRead>): VideoRead => ({
  id: 1,
  video_id: 'abc123DEF45',
  title: null,
  transcript_status: 'ready',
  metadata: null,
  summary: null,
  overview_status: 'ready',
  suggested_questions: null,
  key_points: null,
  created_at: '2026-10-19T00:00:00Z',
  updated_at: '2026-10-19T00:00:00Z',
  ...fields,
});

describe('videoHasPendingWork', () => {
  it('polls while the transcript is pending or the overview is queued', () => {
    expect(videoHasPendingWork(video({ transcript_status: 'pending', overview_status: 'pending' }))).toBe(true);
    expect(videoHasPendingWork(video({ overview_status: 'queued' }))).toBe(true);
  });

  it('stops once every job has settled, including failures', () => {
    expect(videoHasPendingWork(video({}))).toBe(false);
    expect(videoHasPendingWork(video({ overview_status: 'failed' }))).toBe(false);
    expect(videoHasPendingWork(video({ transcript_status: 'unavailable', overview_status: 'no_transcript' }))).toBe(false);
    expect(videoHasPendingWork(undefined)).toBe(false);
  });
});
