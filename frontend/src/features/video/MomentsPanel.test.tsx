// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { MomentRead } from '../../api';
import MomentsPanel from './MomentsPanel';

let data: Partial<MomentRead>[] = [];
vi.mock('./queries', () => ({ useVideoMoments: () => ({ data, isPending: false, isError: false }) }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({}) }));
vi.mock('../moments/MomentItem', () => ({
  default: ({ moment, arrivedAt }: { moment: MomentRead; arrivedAt?: number | null }) => (
    <li id={`moment-${moment.id}`} data-arrived={arrivedAt === undefined ? 'no' : String(arrivedAt)} />
  ),
}));
const scrolled: string[] = [];
beforeEach(() => {
  data = [{ id: 1 }, { id: 2 }];
  scrolled.length = 0;
  Element.prototype.scrollIntoView = vi.fn(function (this: Element) { scrolled.push(this.id); });
});
afterEach(() => { cleanup(); });

it('scrolls to an arrival once and starts its clock when the row appears', () => {
  const onShown = vi.fn();
  data = [];
  const { rerender, container } = render(<MomentsPanel videoId="v" onSeek={vi.fn()} arrival={{ target: 2, key: 1, shownAt: null }} onArrivalShown={onShown} />);
  expect(onShown).not.toHaveBeenCalled();
  // The new moment arrives with the next refetch.
  data = [{ id: 1 }, { id: 2 }];
  rerender(<MomentsPanel videoId="v" onSeek={vi.fn()} arrival={{ target: 2, key: 1, shownAt: null }} onArrivalShown={onShown} />);
  expect(scrolled).toEqual(['moment-2']);
  expect(onShown).toHaveBeenCalledWith(1);
  expect(container.querySelector('#moment-2')!.getAttribute('data-arrived')).toBe('null');
  expect(container.querySelector('#moment-1')!.getAttribute('data-arrived')).toBe('no');

  // Polling brings new data; the list stays where the user put it.
  data = [{ id: 1 }, { id: 2 }, { id: 3 }];
  rerender(<MomentsPanel videoId="v" onSeek={vi.fn()} arrival={{ target: 2, key: 1, shownAt: 100 }} onArrivalShown={onShown} />);
  expect(scrolled).toEqual(['moment-2']);
  expect(onShown).toHaveBeenCalledTimes(1);
  expect(container.querySelector('#moment-2')!.getAttribute('data-arrived')).toBe('100');

  // View moment again: a new key scrolls and replays.
  rerender(<MomentsPanel videoId="v" onSeek={vi.fn()} arrival={{ target: 2, key: 2, shownAt: null }} onArrivalShown={onShown} />);
  expect(scrolled).toEqual(['moment-2', 'moment-2']);
  expect(onShown).toHaveBeenLastCalledWith(2);
});

it('does not scroll again when it remounts after an arrival was shown', () => {
  render(<MomentsPanel videoId="v" onSeek={vi.fn()} arrival={{ target: 2, key: 1, shownAt: 100 }} onArrivalShown={vi.fn()} />);
  expect(scrolled).toEqual([]);
});
