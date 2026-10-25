import { useMemo } from 'react';
import { toastApiError } from '../api/errors';
import { useToast } from './useToast';

/** Toasts for action results; API errors already handled elsewhere stay quiet. */
export function useNotify() {
  const { addToast } = useToast();
  return useMemo(() => ({
    error: (cause: unknown, title: string, fallback: string) =>
      toastApiError(addToast, cause, title, fallback),
    success: (title: string, message = '', action?: { label: string; onClick: () => void }) => addToast({ title, message, type: 'success', action }),
    info: (title: string, message = '') => addToast({ title, message, type: 'info' }),
  }), [addToast]);
}
