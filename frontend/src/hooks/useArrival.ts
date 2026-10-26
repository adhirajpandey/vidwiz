import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { ARRIVAL_HOLD_MS, arrivalPhase, prefersReducedMotion } from '../lib/arrival';

export interface Arrival<T> {
  target: T;
  /** Changes on every arrival, so reaching the same target again replays it. */
  key: number;
  /** When the target was first on screen; its clock starts then. */
  shownAt: number | null;
}

/** The latest arrival. `arrive` starts a new one; `shown` starts its clock once. */
export function useArrival<T>(initial: T | null) {
  const [arrival, setArrival] = useState<Arrival<T> | null>(() => (initial === null ? null : { target: initial, key: 1, shownAt: null }));
  const arrive = useCallback((target: T) => setArrival(previous => ({ target, key: (previous?.key ?? 0) + 1, shownAt: null })), []);
  const shown = useCallback((key: number) => setArrival(previous => (
    previous?.key === key && previous.shownAt === null ? { ...previous, shownAt: Date.now() } : previous
  )), []);
  return { arrival, arrive, shown };
}

/**
 * The arrival tint for a target shown at `shownAt`: `null` while it waits to be
 * shown, `undefined` when it is not the target. The clock comes from `shownAt`,
 * so rerenders, polling, and remounts continue it instead of starting again.
 */
export function useArrivalTint(shownAt: number | null | undefined): { className?: string; style?: CSSProperties } {
  const [, setTick] = useState(0);
  const elapsed = shownAt == null ? 0 : Date.now() - shownAt;
  const { phase, changesIn } = shownAt === undefined ? { phase: 'off', changesIn: null } : arrivalPhase(elapsed, prefersReducedMotion());
  useEffect(() => {
    if (shownAt == null || changesIn === null) return;
    const timer = setTimeout(() => setTick(tick => tick + 1), changesIn);
    return () => clearTimeout(timer);
  }, [shownAt, changesIn]);
  if (phase === 'on') return { className: 'arrival' };
  // A negative delay continues a fade already under way, as after a remount.
  if (phase === 'fading') return { className: 'arrival-fading', style: { animationDelay: `${ARRIVAL_HOLD_MS - elapsed}ms` } };
  return {};
}
