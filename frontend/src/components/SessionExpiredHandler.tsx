import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  SESSION_EXPIRED_EVENT,
  type SessionExpiredDetail,
} from '../api/session';
import { useToast } from '../hooks/useToast';
import { removeToken } from '../lib/authUtils';

export default function SessionExpiredHandler() {
  const location = useLocation();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const lastHandledAtRef = useRef(0);

  useEffect(() => {
    const handleSessionExpired = (event: Event) => {
      const now = Date.now();
      if (now - lastHandledAtRef.current < 1000) return;
      lastHandledAtRef.current = now;

      const detail = (event as CustomEvent<SessionExpiredDetail>).detail;
      removeToken();
      addToast({
        title: 'Session expired',
        message: 'Please sign in again to continue.',
        type: 'error',
        durationMs: 6000,
        referenceId: detail?.requestId,
      });

      if (
        location.pathname !== '/login' &&
        location.pathname !== '/signup'
      ) {
        navigate('/login', {
          replace: true,
          state: { from: location.pathname },
        });
      }
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () =>
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
  }, [addToast, location.pathname, navigate]);

  return null;
}
