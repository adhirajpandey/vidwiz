import { useSyncExternalStore } from 'react';

const subscribe = () => () => {};

/** Keep browser-dependent markup identical to the build-time render until hydration finishes. */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}
