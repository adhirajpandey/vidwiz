import { describe, expect, it } from 'vitest';

import { extractStartSeconds, extractVideoId, isValidVideoId } from './videoUtils';

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

describe('isValidVideoId', () => {
  it('accepts 11-character IDs only', () => {
    expect(isValidVideoId('dQw4w9WgXcQ')).toBe(true);
    expect(isValidVideoId('dQw4w9WgXc')).toBe(false);
    expect(isValidVideoId('https://youtu.be/dQw4w9WgXcQ')).toBe(false);
  });
});

describe('extractStartSeconds', () => {
  it.each([
    ['https://youtu.be/dQw4w9WgXcQ?t=133', 133],
    ['https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=2m13s', 133],
    ['youtube.com/watch?v=dQw4w9WgXcQ&t=1h2m3s', 3723],
    ['https://www.youtube.com/embed/dQw4w9WgXcQ?start=90', 90],
    ['https://www.youtube.com/watch?v=dQw4w9WgXcQ#t=45', 45],
  ])('reads the start time from %s', (input, seconds) => {
    expect(extractStartSeconds(input)).toBe(seconds);
  });

  it.each(['https://youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ', 'https://youtu.be/dQw4w9WgXcQ?t=soon', ''])('returns 0 without a usable time: %s', (input) => {
    expect(extractStartSeconds(input)).toBe(0);
  });
});
