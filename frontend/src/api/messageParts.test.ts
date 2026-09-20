import { describe, expect, it } from 'vitest';
import { parseWizEvent } from './messageParts';

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
