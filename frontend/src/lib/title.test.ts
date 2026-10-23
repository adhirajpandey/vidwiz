import { describe, expect, it } from 'vitest';
import { documentTitle, shortTitle } from './title';

describe('documentTitle', () => {
  it('joins parts most specific first and ends with the product name', () => {
    expect(documentTitle('A talk', 'Moments')).toBe('A talk · Moments · VidWiz');
    expect(documentTitle()).toBe('VidWiz');
  });
});

describe('shortTitle', () => {
  it('collapses whitespace and keeps short text whole', () => {
    expect(shortTitle('  What did\n I save   yesterday? ')).toBe('What did I save yesterday?');
  });

  it('cuts long text at a word boundary', () => {
    expect(shortTitle('one two three four', 12)).toBe('one two…');
    expect(shortTitle('one two, three four', 9)).toBe('one two…');
  });

  it('cuts a single long word', () => {
    expect(shortTitle('abcdefghij', 4)).toBe('abcd…');
  });
});
