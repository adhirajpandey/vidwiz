import { useSyncExternalStore } from 'react';

// one row at a time edits its note or confirms a delete, like the extension.
type Active = { id: number; mode: 'edit' | 'delete' } | null;
let active: Active = null;
const listeners = new Set<() => void>();
export function setActiveRow(next: Active) {
  active = next;
  listeners.forEach(listener => listener());
}
export function clearActiveRow(id: number, mode?: 'edit' | 'delete'): boolean {
  if (active?.id !== id || (mode && active.mode !== mode)) return false;
  setActiveRow(null);
  return true;
}
export function useActiveRow(): Active {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => listeners.delete(listener); }, () => active);
}
