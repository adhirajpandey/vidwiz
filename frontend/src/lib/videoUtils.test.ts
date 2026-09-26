import { describe, expect, it } from 'vitest';

import { extractVideoId, timestampToSeconds } from './videoUtils';

describe('extractVideoId', () => {
  it('normalizes a malformed single-slash HTTPS protocol', () => {
    expect(extractVideoId('https:/youtu.be/dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ');
  });

  it.each([
    'dQw4w9WgXcQ',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'youtube.com/shorts/dQw4w9WgXcQ',
    'https://m.youtube.com/live/dQw4w9WgXcQ?feature=share',
    'https://www.youtube.com/embed/dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ?t=42',
  ])('extracts the ID from %s', (input) => {
    expect(extractVideoId(input)).toBe('dQw4w9WgXcQ');
  });

  it.each([
    '',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123',
    'https://www.youtube.com/shorts/dQw4w9WgXcQ/extra',
    'https://example.com/watch?v=dQw4w9WgXcQ',
    'not a url',
  ])('rejects %s', (input) => {
    expect(extractVideoId(input)).toBeNull();
  });
});

describe('timestampToSeconds', () => {
  it.each([['0:07', 7], ['12:34', 754], ['1:02:03', 3723]])('converts %s', (input, seconds) => {
    expect(timestampToSeconds(input)).toBe(seconds);
  });
});
