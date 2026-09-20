import { useCallback, useEffect, useRef, useState } from 'react';
import { authApi } from '../api';

export type CreditBalanceState =
  | { status: 'idle' | 'loading'; balance: null }
  | { status: 'success'; balance: number }
  | { status: 'error'; balance: null };

export function useCreditBalance(enabled: boolean, accountKey: string | null) {
  const [state, setState] = useState<CreditBalanceState>({ status: 'idle', balance: null });
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    if (!enabled || !accountKey) return;

    const requestId = ++requestIdRef.current;
    setState({ status: 'loading', balance: null });
    try {
      const profile = await authApi.getMe();
      if (requestId === requestIdRef.current) {
        setState({ status: 'success', balance: profile.credits_balance });
      }
    } catch {
      if (requestId === requestIdRef.current) {
        setState({ status: 'error', balance: null });
      }
    }
  }, [accountKey, enabled]);

  useEffect(() => {
    if (!enabled || !accountKey) {
      requestIdRef.current += 1;
      setState({ status: 'idle', balance: null });
      return;
    }

    void load();
    const handleFocus = () => void load();
    window.addEventListener('focus', handleFocus);
    return () => {
      requestIdRef.current += 1;
      window.removeEventListener('focus', handleFocus);
    };
  }, [accountKey, enabled, load]);

  return { ...state, retry: load };
}
