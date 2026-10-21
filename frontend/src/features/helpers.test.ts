import { describe, expect, it } from 'vitest';
import type { FeedMoment, MomentResult, PassageResult } from '../api';
import type { WizMessage } from '../hooks/useWizChat';
import { dayLabel, formatClock } from '../lib/format';
import { citedVideoIds } from './ask/citations';
import { groupFeed } from './home/groupFeed';
import { resultLink } from './search/resultLink';
import { phoneCaptureExample } from './settings/phoneCapture';
import { sharedVideoId } from './share/sharedVideoId';
import { activeSegment } from './video/activeSegment';

function moment(id: number, videoId: string | null, createdAt: string): FeedMoment {
  return {
    id, video_id: videoId, at_seconds: 10, quote: null, quote_start_seconds: null, ai_text: null, note: null,
    ai_status: 'not_requested', resolve_status: videoId ? 'resolved' : 'resolving', source: 'web',
    pending_title: null, resolve_candidates: null, created_at: createdAt, updated_at: createdAt,
    video_title: null, video_metadata: null,
  };
}

describe('formatClock', () => {
  it('formats minutes and hours', () => {
    expect(formatClock(0)).toBe('0:00');
    expect(formatClock(83.9)).toBe('1:23');
    expect(formatClock(3725)).toBe('1:02:05');
  });
});

describe('dayLabel', () => {
  it('names today and yesterday', () => {
    const now = new Date(2026, 9, 19, 12);
    expect(dayLabel(new Date(2026, 9, 19, 1).toISOString(), now)).toBe('Today');
    expect(dayLabel(new Date(2026, 9, 18, 23).toISOString(), now)).toBe('Yesterday');
  });
});

describe('groupFeed', () => {
  it('groups consecutive moments by video and day', () => {
    const today = new Date().toISOString();
    const groups = groupFeed([
      moment(3, 'aaaaaaaaaaa', today),
      moment(2, 'aaaaaaaaaaa', today),
      moment(1, 'bbbbbbbbbbb', today),
      moment(0, null, today),
    ]);
    expect(groups.map(group => group.moments.map(item => item.id))).toEqual([[3, 2], [1], [0]]);
  });
});

describe('resultLink', () => {
  const video = { video_id: 'aaaaaaaaaaa', title: null, thumbnail_url: '' };
  it('opens passages at their time and moments highlighted', () => {
    const passage: PassageResult = { kind: 'passage', video, chunk_id: 1, start_seconds: 42.7, end_seconds: 80, snippet: [], score: 1 };
    const found = { kind: 'moment', video, start_seconds: 12, snippet: [], score: 1, moment: { id: 9, at_seconds: 12, quote_start_seconds: 0 } } as unknown as MomentResult;
    expect(resultLink(passage)).toBe('/v/aaaaaaaaaaa?t=42');
    expect(resultLink(found)).toBe('/v/aaaaaaaaaaa?t=9&m=9');
  });
});

describe('sharedVideoId', () => {
  it('finds a YouTube video in shared text', () => {
    expect(sharedVideoId(new URLSearchParams({ text: 'Watch this https://youtu.be/dQw4w9WgXcQ now' }))).toBe('dQw4w9WgXcQ');
    expect(sharedVideoId(new URLSearchParams({ url: 'https://example.com' }))).toBeNull();
  });
});

describe('activeSegment', () => {
  const segments = [0, 5, 10].map(start => ({ start_seconds: start, end_seconds: start + 5, text: `${start}` }));
  it('finds the segment playing now', () => {
    expect(activeSegment(segments, null)).toBe(-1);
    expect(activeSegment(segments, 7)).toBe(1);
    expect(activeSegment(segments, 99)).toBe(2);
  });
});

describe('citedVideoIds', () => {
  it('collects video ids from block citations once', () => {
    const passage = (videoId: string | null) => ({ chunk_ids: ['c'], start_seconds: 0, end_seconds: 1, video_id: videoId });
    const messages: WizMessage[] = [{
      id: 'a', role: 'assistant', createdAt: new Date(), parts: [{
        type: 'block', text: 'x', citations: [{ list_item_index: null, passages: [passage('v1'), passage(null), passage('v1'), passage('v2')] }],
      }],
    }];
    expect(citedVideoIds(messages)).toEqual(['v1', 'v2']);
  });
});

describe('phoneCaptureExample', () => {
  it('shows the capture request for the configured API', () => {
    expect(phoneCaptureExample('https://api.example/v2')).toContain('POST https://api.example/v2/captures');
  });
});
