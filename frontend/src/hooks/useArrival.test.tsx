// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useArrival, useArrivalTint } from './useArrival';

let reduced = false;
beforeEach(() => {
  reduced = false;
  vi.useFakeTimers();
  vi.stubGlobal('matchMedia', () => ({ matches: reduced }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function Row({ shownAt, label = 'row' }: { shownAt: number | null | undefined; label?: string }) {
  const tint = useArrivalTint(shownAt);
  return <div data-testid={label} className={tint.className} style={tint.style} />;
}
const row = (label = 'row') => screen.getByTestId(label);

describe('useArrivalTint', () => {
  it('tints until shown, holds, fades completely, then clears', () => {
    const { rerender } = render(<Row shownAt={null} />);
    expect(row().className).toBe('arrival');
    const shownAt = Date.now();
    rerender(<Row shownAt={shownAt} />);
    act(() => { vi.advanceTimersByTime(2499); });
    expect(row().className).toBe('arrival');
    act(() => { vi.advanceTimersByTime(1); });
    expect(row().className).toBe('arrival-fading');
    expect(row().style.animationDelay).toBe('0ms');
    act(() => { vi.advanceTimersByTime(900); });
    expect(row().className).toBe('');
  });

  it('keeps its clock through rerenders and remounts', () => {
    const shownAt = Date.now();
    const { rerender, unmount } = render(<Row shownAt={shownAt} />);
    act(() => { vi.advanceTimersByTime(2000); });
    rerender(<Row shownAt={shownAt} />);
    act(() => { vi.advanceTimersByTime(500); });
    expect(row().className).toBe('arrival-fading');
    act(() => { vi.advanceTimersByTime(300); });
    unmount();
    // A remount mid-fade continues the fade where it was.
    render(<Row shownAt={shownAt} />);
    expect(row().className).toBe('arrival-fading');
    expect(row().style.animationDelay).toBe('-300ms');
    act(() => { vi.advanceTimersByTime(600); });
    expect(row().className).toBe('');
  });

  it('clears after the hold without fading when motion is reduced', () => {
    reduced = true;
    render(<Row shownAt={Date.now()} />);
    act(() => { vi.advanceTimersByTime(2500); });
    expect(row().className).toBe('');
  });

  it('leaves rows that were not reached alone', () => {
    render(<Row shownAt={undefined} />);
    expect(row().className).toBe('');
  });
});

describe('useArrival', () => {
  function Target() {
    const { arrival, arrive, shown } = useArrival<number>(7);
    return <>
      <output data-testid="arrival">{JSON.stringify(arrival)}</output>
      <button onClick={() => arrive(7)}>Again</button>
      <button onClick={() => arrival && shown(arrival.key)}>Shown</button>
    </>;
  }
  const state = () => JSON.parse(screen.getByTestId('arrival').textContent!);

  it('replays the same target with a new key and starts each clock once', () => {
    render(<Target />);
    expect(state()).toEqual({ target: 7, key: 1, shownAt: null });
    act(() => screen.getByText('Shown').click());
    const first = state().shownAt;
    expect(first).toBe(Date.now());
    act(() => { vi.advanceTimersByTime(1000); });
    act(() => screen.getByText('Shown').click());
    expect(state().shownAt).toBe(first);
    act(() => screen.getByText('Again').click());
    expect(state()).toEqual({ target: 7, key: 2, shownAt: null });
  });
});
