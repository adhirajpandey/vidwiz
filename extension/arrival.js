// The just-saved moment's tint: it holds, then fades away completely. Same
// timing as frontend/src/lib/arrival.ts; change both together.
export const ARRIVAL_HOLD_MS = 2500;
export const ARRIVAL_FADE_MS = 900;

/** The phase `elapsed` ms after the moment was first shown, and how long until it changes. */
export function arrivalPhase(elapsed, reducedMotion) {
  if (elapsed < ARRIVAL_HOLD_MS) return { phase: "on", changesIn: ARRIVAL_HOLD_MS - elapsed };
  // Without motion the tint simply clears when the hold ends.
  if (reducedMotion) return { phase: "off", changesIn: null };
  const end = ARRIVAL_HOLD_MS + ARRIVAL_FADE_MS;
  return elapsed < end ? { phase: "fading", changesIn: end - elapsed } : { phase: "off", changesIn: null };
}
