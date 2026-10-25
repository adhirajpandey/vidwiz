import { describe, expect, it } from 'vitest';
import type { SearchResult } from '../../api';
import { resultLink } from './resultLink';

describe('resultLink', () => {
  it('opens a moment with its highlight, panel and playback lead-in', () => {
    const result = { kind: 'moment', video: { video_id: 'aaaaaaaaaaa' }, moment: { id: 42, at_seconds: 20 } } as SearchResult;
    expect(resultLink(result)).toBe('/v/aaaaaaaaaaa?t=17&m=42&tab=moments');
  });
  it('opens a passage in Transcript at its start', () => {
    const result = { kind: 'passage', video: { video_id: 'aaaaaaaaaaa' }, start_seconds: 20.5 } as SearchResult;
    expect(resultLink(result)).toBe('/v/aaaaaaaaaaa?t=20&tab=transcript');
  });
});
