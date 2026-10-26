// Arrival highlights point at what you just reached: a moment opened from a
// link or View moment, or a video just added. The tint holds, then fades away
// completely. State highlights (the playing line, the open chat) never use this.
export const ARRIVAL_HOLD_MS = 2500;
export const ARRIVAL_FADE_MS = 900;

export type ArrivalPhase = 'on' | 'fading' | 'off';

/** The phase `elapsed` ms after the target was first shown, and how long until it changes. */
export function arrivalPhase(elapsed: number, reducedMotion: boolean): { phase: ArrivalPhase; changesIn: number | null } {
  if (elapsed < ARRIVAL_HOLD_MS) return { phase: 'on', changesIn: ARRIVAL_HOLD_MS - elapsed };
  // Without motion the tint simply clears when the hold ends.
  if (reducedMotion) return { phase: 'off', changesIn: null };
  const end = ARRIVAL_HOLD_MS + ARRIVAL_FADE_MS;
  return elapsed < end ? { phase: 'fading', changesIn: end - elapsed } : { phase: 'off', changesIn: null };
}

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}
