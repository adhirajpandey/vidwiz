import { describe, expect, it } from 'vitest';

import { extractVideoId, timestampToSeconds } from './videoUtils';

describe('extractVideoId', () => {
  it('normalizes a malformed single-slash HTTPS protocol', () => {
    expect(extractVideoId('https:/youtu.be/dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ');
  });
});

describe('timestampToSeconds', () => {
  it.each([['0:07', 7], ['12:34', 754], ['1:02:03', 3723]])('converts %s', (input, seconds) => {
    expect(timestampToSeconds(input)).toBe(seconds);
  });
});
