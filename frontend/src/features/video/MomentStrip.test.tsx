// @vitest-environment jsdom
import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MomentRead } from '../../api';
import { playFrom } from '../moments/queries';
import MomentStrip from './MomentStrip';
import { GROUP_PX, groupMarks } from './groupMarks';

// A dense, made-up video: 50 moments scattered over 4h15m.
const DURATION = 15_300;
let seed = 7;
const dense = Array.from({ length: 50 }, (_, index) => {
  seed = (seed * 48_271) % 2_147_483_647;
  return { id: index + 1, at_seconds: seed % DURATION };
});

describe('groupMarks', () => {
  it('keeps every moment and leaves at least 22px between markers', () => {
    for (const width of [340, 900, 1400]) {
      const groups = groupMarks(dense, DURATION, width);
      expect(groups.flat()).toHaveLength(50);
      const starts = groups.map(group => (group[0].at_seconds / DURATION) * width);
      starts.slice(1).forEach((start, index) => expect(start - starts[index]).toBeGreaterThanOrEqual(GROUP_PX));
      groups.flat().slice(1).forEach((moment, index) => expect(moment.at_seconds).toBeGreaterThanOrEqual(groups.flat()[index].at_seconds));
    }
  });

  it('merges more on narrow rails and nothing before the rail is measured', () => {
    expect(groupMarks(dense, DURATION, 340).length).toBeLessThan(groupMarks(dense, DURATION, 900).length);
    expect(groupMarks(dense, DURATION, 0)).toHaveLength(50);
  });
});

let moments: Partial<MomentRead>[] = [];
vi.mock('./queries', () => ({ useVideoMoments: () => ({ data: moments }) }));
let resize: (width: number) => void;
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class {
    callback: ResizeObserverCallback;
    constructor(callback: ResizeObserverCallback) { this.callback = callback; }
    // Only the rail's observer resizes; tooltips and menus watch their own content.
    observe(element: Element) {
      if (element.getAttribute('role') === 'group') resize = width => this.callback([{ contentRect: { width } } as ResizeObserverEntry], this as unknown as ResizeObserver);
    }
    unobserve() {}
    disconnect() {}
  });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: 200 } as DOMRect);
  moments = [
    { id: 1, at_seconds: 100, ai_text: 'Opening idea', resolve_status: 'resolved' },
    { id: 2, at_seconds: 120, note: 'My note', resolve_status: 'resolved' },
    { id: 3, at_seconds: 130, quote: 'What was said', resolve_status: 'resolved' },
    { id: 4, at_seconds: 600, ai_text: 'Later point', resolve_status: 'resolved' },
    { id: 5, at_seconds: 700, resolve_status: 'resolving' },
  ];
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('groups close moments into one numbered marker whose menu seeks', async () => {
  const onSeek = vi.fn();
  const user = userEvent.setup();
  render(<MomentStrip videoId="v" duration={1000} playhead={null} onSeek={onSeek} />);
  const markers = within(screen.getByRole('group', { name: 'Your moments in this video' })).getAllByRole('button');
  expect(markers.map(marker => marker.getAttribute('aria-label'))).toEqual(['3 moments, 1:40 to 2:10', 'Play moment at 10:00']);

  await user.click(markers[1]);
  expect(onSeek).toHaveBeenLastCalledWith(playFrom(moments[3] as MomentRead));

  await user.click(markers[0]);
  const items = screen.getAllByRole('menuitem');
  expect(items.map(item => item.textContent)).toEqual(['1:40Opening idea', '2:00My note', '2:10What was said']);
  await user.click(items[1]);
  expect(onSeek).toHaveBeenLastCalledWith(playFrom(moments[1] as MomentRead));
});

it('is one tab stop per marker and regroups when the rail resizes', async () => {
  const user = userEvent.setup();
  render(<MomentStrip videoId="v" duration={1000} playhead={null} onSeek={vi.fn()} />);
  await user.tab();
  expect(document.activeElement?.getAttribute('aria-label')).toBe('3 moments, 1:40 to 2:10');
  await user.tab();
  expect(document.activeElement?.getAttribute('aria-label')).toBe('Play moment at 10:00');
  await user.tab();
  expect(document.activeElement).toBe(document.body);

  act(() => resize(4000));
  expect(screen.getAllByRole('button').map(marker => marker.getAttribute('aria-label'))).toEqual([
    'Play moment at 1:40', 'Play moment at 2:00', 'Play moment at 2:10', 'Play moment at 10:00',
  ]);
});
