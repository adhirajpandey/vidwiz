import { describe, expect, it } from 'vitest';
import { arrivalPhase } from './arrival';

describe('arrivalPhase', () => {
  it('holds the tint for 2.5 seconds, then fades over 900 ms', () => {
    expect(arrivalPhase(0, false)).toEqual({ phase: 'on', changesIn: 2500 });
    expect(arrivalPhase(2499, false)).toEqual({ phase: 'on', changesIn: 1 });
    expect(arrivalPhase(2500, false)).toEqual({ phase: 'fading', changesIn: 900 });
    expect(arrivalPhase(3000, false)).toEqual({ phase: 'fading', changesIn: 400 });
    expect(arrivalPhase(3400, false)).toEqual({ phase: 'off', changesIn: null });
  });

  it('clears without a fade when motion is reduced', () => {
    expect(arrivalPhase(1000, true)).toEqual({ phase: 'on', changesIn: 1500 });
    expect(arrivalPhase(2500, true)).toEqual({ phase: 'off', changesIn: null });
  });
});
