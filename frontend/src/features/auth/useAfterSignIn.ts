import { useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

/** Where to go after signing in: a safe in-app `next` path, or Home. */
export function useAfterSignIn() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  return useCallback(() => {
    const next = params.get('next');
    navigate(next && next.startsWith('/') && !next.startsWith('//') ? next : '/', { replace: true });
  }, [params, navigate]);
}
