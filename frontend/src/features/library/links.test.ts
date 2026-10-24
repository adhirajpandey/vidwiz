import { expect, it } from 'vitest';
import { linkTime, looksLikeLink } from './links';

it('distinguishes ordinary search words from YouTube URLs', () => {
  expect(looksLikeLink('performance')).toBe(false);
  expect(looksLikeLink('youtube.com/@channel')).toBe(true);
  expect(looksLikeLink('https://youtu.be/aaaaaaaaaaa?t=754')).toBe(true);
  expect(looksLikeLink('https://youtube.com.evil.test/watch?v=aaaaaaaaaaa')).toBe(false);
});
it('preserves the supported timestamp forms and rejects invalid times', () => {
  for (const suffix of ['?t=90', '?t=1m30s', '?start=90', '#t=90s']) expect(linkTime(`https://youtu.be/aaaaaaaaaaa${suffix}`)).toBe(90);
  expect(linkTime('youtu.be/aaaaaaaaaaa?t=1h2m3s')).toBe(3723);
  expect(linkTime('youtu.be/aaaaaaaaaaa?t=-5')).toBeNull();
  expect(linkTime('youtu.be/aaaaaaaaaaa?t=oops')).toBeNull();
});
