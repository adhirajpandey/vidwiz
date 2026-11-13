// Node 25 and later define their own localStorage and sessionStorage globals,
// which stay undefined unless Node is started with --localstorage-file.
// Vitest's jsdom environment only copies window properties that the global
// does not already have, so jsdom's storage would never be installed. Point
// both globals at the jsdom window's storage instead.
const dom = (globalThis as { jsdom?: { window: Window } }).jsdom

if (dom) {
  for (const key of ["localStorage", "sessionStorage"] as const) {
    Object.defineProperty(globalThis, key, {
      value: dom.window[key],
      configurable: true,
      writable: true,
    })
  }
}
