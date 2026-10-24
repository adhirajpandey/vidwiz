import { useSyncExternalStore } from 'react';

// one row at a time edits its note or confirms a delete, like the extension.
type Active = { id: number; mode: 'edit' | 'delete' } | null;
let active: Active = null;
const listeners = new Set<() => void>();
export function setActiveRow(next: Active) {
  active = next;
  listeners.forEach(listener => listener());
}
export function clearActiveRow(id: number) { if (active?.id === id) setActiveRow(null); }
export function useActiveRow(): Active {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => listeners.delete(listener); }, () => active);
}
