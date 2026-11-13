import { describe, expect, it } from 'vitest';
import { hasContent, parseWizEvent, readStoredParts } from './messageParts';

const digest = {
  type: 'digest', since: '2026-11-07', until: '2026-11-14', total_moments: 3, video_count: 1,
  videos: [{ video_id: 'abc123DEF45', title: null, moment_count: 3, moments: [{ id: 'm1', at_seconds: 75, text: 'Batch the reviews' }] }],
};
const stats = { type: 'stats', video_count: null, group_by: 'channel', groups: [{ name: 'Talks', videos: 4 }] };

describe('library stream kinds', () => {
  it('parses status, digest, and stats', () => {
    expect(parseWizEvent({ type: 'status', text: 'Searching your library' })).toEqual({ type: 'status', text: 'Searching your library' });
    expect(parseWizEvent(digest)).toEqual(digest);
    expect(parseWizEvent(stats)).toEqual(stats);
    const count = { type: 'stats', video_count: 12, group_by: null, groups: null };
    expect(parseWizEvent(count)).toEqual(count);
  });
  it.each([
    { type: 'status', text: '' },
    { type: 'status' },
    { ...digest, since: 'last week' },
    { ...digest, total_moments: -1 },
    { ...digest, videos: [{ ...digest.videos[0], moments: [{ id: 'm1', at_seconds: -1, text: 'x' }] }] },
    { ...digest, videos: [{ ...digest.videos[0], title: 3 }] },
    { ...stats, group_by: 'year' },
    { ...stats, groups: [{ name: 'Talks', videos: 1.5 }] },
    { type: 'stats', video_count: 2 },
  ])('skips malformed new kind %o', event => expect(parseWizEvent(event)).toBeNull());
  it.each(['2026-02-30', '2026-99-99', '2026-13-01', '2026-00-10', '2025-02-29', '2100-02-29'])('skips a digest dated %s in stream and history', date => {
    expect(parseWizEvent({ ...digest, since: date })).toBeNull();
    expect(parseWizEvent({ ...digest, until: date })).toBeNull();
    expect(readStoredParts([{ ...digest, since: date }])).toEqual([]);
  });
  it.each(['2024-02-29', '2000-02-29', '2026-12-31'])('accepts the real day %s', date => {
    expect(parseWizEvent({ ...digest, since: date, until: date })).toMatchObject({ since: date, until: date });
  });
  it.each([{ type: 'video_list', videos: [] }, { type: 'tool' }, {}])('skips unknown kind %o', event => {
    expect(parseWizEvent(event)).toBeNull();
  });
  it.each([null, [], 'text', { type: 'text', text: 1 }, { type: 'done', message_id: 0 }, { type: 'error', message: '' }])('still rejects %o', event => {
    expect(() => parseWizEvent(event)).toThrow();
  });
  it('counts digests and stats as answer content', () => {
    expect(hasContent(digest as never)).toBe(true);
    expect(hasContent({ type: 'text', text: '  ' })).toBe(false);
    expect(hasContent({ type: 'citation', chunk_id: 'c', start_seconds: 0, end_seconds: 1 })).toBe(false);
  });
});

describe('stored parts', () => {
  it('keeps known parts in order and ignores unknown or malformed ones', () => {
    const text = { type: 'text', text: 'Answer' };
    const citation = { type: 'citation', chunk_id: 'c', start_seconds: 1, end_seconds: 2 };
    expect(readStoredParts([text, { type: 'video_list', videos: [] }, citation, digest, { type: 'status', text: 'x' },
      { ...stats, groups: 'many' }, stats, null])).toEqual([text, citation, digest, stats]);
  });
});

describe('block stream validation', () => {
  const block = { type: 'block', text: 'Answer', citations: [{ list_item_index: null, passages: [{ chunk_ids: ['a'], start_seconds: 1, end_seconds: 3 }] }] };
  it('retains source associations and ranges', () => expect(parseWizEvent(block)).toEqual(block));
  it.each([-1, 1.5, '0', undefined])('rejects invalid target %s', target => {
    expect(() => parseWizEvent({ ...block, citations: [{ ...block.citations[0], list_item_index: target }] })).toThrow();
  });
  it.each([{ start_seconds: -1 }, { end_seconds: 0 }, { end_seconds: Infinity }, { chunk_ids: [] }, { chunk_ids: [3] }])('rejects invalid passage %s', patch => {
    expect(() => parseWizEvent({ ...block, citations: [{ list_item_index: null, passages: [{ ...block.citations[0].passages[0], ...patch }] }] })).toThrow();
  });
});
