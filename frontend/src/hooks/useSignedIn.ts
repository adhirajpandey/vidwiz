import { useSyncExternalStore } from 'react';
import { AUTH_CHANGED_EVENT, isAuthenticated } from '../lib/authUtils';

function subscribe(onChange: () => void): () => void {
  window.addEventListener(AUTH_CHANGED_EVENT, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(AUTH_CHANGED_EVENT, onChange);
    window.removeEventListener('storage', onChange);
  };
}

/** Whether a valid session token exists; re-renders on login and logout. */
export function useSignedIn(): boolean {
  return useSyncExternalStore(subscribe, isAuthenticated, () => false);
}
