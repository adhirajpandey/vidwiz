import assert from "node:assert/strict";
import { test } from "node:test";
import { arrivalPhase } from "./arrival.js";

test("holds the tint for 2.5 seconds, then fades over 900 ms", () => {
  assert.deepEqual(arrivalPhase(0, false), { phase: "on", changesIn: 2500 });
  assert.deepEqual(arrivalPhase(2500, false), { phase: "fading", changesIn: 900 });
  assert.deepEqual(arrivalPhase(3100, false), { phase: "fading", changesIn: 300 });
  assert.deepEqual(arrivalPhase(3400, false), { phase: "off", changesIn: null });
});

test("clears without a fade when motion is reduced", () => {
  assert.deepEqual(arrivalPhase(2000, true), { phase: "on", changesIn: 500 });
  assert.deepEqual(arrivalPhase(2500, true), { phase: "off", changesIn: null });
});
