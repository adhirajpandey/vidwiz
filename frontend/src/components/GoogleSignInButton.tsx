import { useEffect, useRef, useState } from 'react';
import config from '../config';
import Button from './ui/Button';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              type?: string;
              theme?: string;
              size?: string;
              text?: string;
              shape?: string;
              width?: number | string;
            }
          ) => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => void;
  onError: (error: string) => void;
}

const SCRIPT_URL = 'https://accounts.google.com/gsi/client';
const initialized = new WeakSet<object>();
let receiveCredential: ((response: { credential: string }) => void) | undefined;

export default function GoogleSignInButton({ onSuccess, onError }: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onSuccess, onError });
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable'>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => { callbacks.current = { onSuccess, onError }; }, [onSuccess, onError]);

  useEffect(() => {
    const container = buttonRef.current;
    if (!config.GOOGLE_CLIENT_ID || !container) return;
    let stopped = false;
    let rendered = '';
    let ready = false;
    const receive = (response: { credential: string }) => {
      if (response.credential) callbacks.current.onSuccess(response.credential);
      else callbacks.current.onError('No credential received from Google');
    };
    receiveCredential = receive;
    let script = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_URL}"]`);
    // A retry replaces only a failed/missing script, never an initialized client.
    if (!window.google?.accounts?.id && (!script || attempt > 0)) {
      script?.remove();
      script = document.createElement('script');
      script.src = SCRIPT_URL;
      script.async = true;
      document.head.appendChild(script);
    }
    const fail = () => {
      if (stopped || ready) return;
      stopped = true;
      clearInterval(poll);
      clearTimeout(timeout);
      container.replaceChildren();
      setState('unavailable');
    };
    const render = () => {
      const client = window.google?.accounts?.id;
      if (stopped || !client) return;
      try {
        if (!initialized.has(client)) {
          client.initialize({ client_id: config.GOOGLE_CLIENT_ID, callback: response => receiveCredential?.(response) });
          initialized.add(client);
        }
        const width = Math.min(400, Math.floor(container.getBoundingClientRect().width));
        const theme = document.documentElement.classList.contains('dark') ? 'filled_black' : 'outline';
        const key = `${width}:${theme}`;
        if (rendered !== key) {
          container.replaceChildren();
          client.renderButton(container, { type: 'standard', theme, size: 'large', text: 'continue_with', shape: 'rectangular', ...(width > 0 ? { width } : {}) });
          rendered = key;
        }
        ready = true;
        clearInterval(poll);
        clearTimeout(timeout);
        setState('ready');
      } catch { fail(); }
    };
    const poll = setInterval(render, 100);
    const timeout = setTimeout(fail, 5000);
    script?.addEventListener('load', render);
    script?.addEventListener('error', fail);
    const resize = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(render) : undefined;
    resize?.observe(container);
    const theme = new MutationObserver(render);
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    render();
    return () => {
      stopped = true;
      clearInterval(poll);
      clearTimeout(timeout);
      script?.removeEventListener('load', render);
      script?.removeEventListener('error', fail);
      resize?.disconnect();
      theme.disconnect();
      container.replaceChildren();
      if (receiveCredential === receive) receiveCredential = undefined;
    };
  }, [attempt]);

  if (!config.GOOGLE_CLIENT_ID) return null;
  return (
    <div className="space-y-2">
      <div ref={buttonRef} className="min-h-10 w-full" />
      {state === 'loading' && <p role="status" className="text-center text-sm text-muted-foreground">Loading Google sign-in…</p>}
      {state === 'unavailable' && <div className="flex flex-wrap items-center justify-center gap-2">
        <p role="status" className="text-sm text-muted-foreground">Google sign-in is unavailable.</p>
        <Button size="sm" onClick={() => { setState('loading'); setAttempt(value => value + 1); }}>Retry</Button>
      </div>}
    </div>
  );
}
