import { describe, expect, it } from 'vitest';

import { extractVideoId } from './videoUtils';

describe('extractVideoId', () => {
  it('normalizes a malformed single-slash HTTPS protocol', () => {
    expect(extractVideoId('https:/youtu.be/dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ');
  });
});
