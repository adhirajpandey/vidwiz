import { useEffect, useRef, useState } from 'react';
import config from '../config';
import type { ChromePort } from '../types/chrome';

function isMessage(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export type CaptureOutcome = 'saved' | 'failed' | 'ignored';
type ShortcutState = {
  state: 'standalone' | 'connecting' | 'connected' | 'outdated' | 'disconnected';
  shortcut: string | null;
};

// A shortcut must not submit a draft, interrupt a menu, or act in a hidden tab.
// An iframe is allowed: the extension can route the command while YouTube owns focus.
export function captureShortcutBlocked() {
  const active = document.activeElement;
  return document.visibilityState === 'hidden'
    || !!active?.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')
    || !!document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"]');
}

export function useCaptureShortcut(capture: () => Promise<CaptureOutcome>): ShortcutState {
  const captureRef = useRef(capture);
  captureRef.current = capture;
  const [status, setStatus] = useState<ShortcutState>({ state: 'standalone', shortcut: 'Alt+S' });

  useEffect(() => {
    const runtime = typeof chrome !== 'undefined' ? chrome.runtime : undefined;
    let disposed = false;
    let port: ChromePort | undefined;
    let connecting = false;
    let connected = false;
    let supported = false;
    let attempt = 0;
    let generation = 0;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let handshake: ReturnType<typeof setTimeout> | undefined;
    const delays = [250, 500, 1_000, 2_000, 5_000, 10_000];

    const scheduleRetry = () => {
      if (disposed || retry !== undefined || attempt >= delays.length) return;
      retry = setTimeout(() => { retry = undefined; connect(); }, delays[attempt++]);
    };
    const connect = () => {
      if (disposed || port || connecting || !runtime?.sendMessage || !runtime.connect) return;
      const openPort = runtime.connect.bind(runtime);
      connecting = true;
      const current = ++generation;
      const unavailable = () => {
        if (disposed || current !== generation) return;
        connecting = connected = false;
        clearTimeout(handshake);
        const previous = port;
        port = undefined;
        previous?.disconnect();
        setStatus(supported ? { state: 'disconnected', shortcut: null } : { state: 'standalone', shortcut: 'Alt+S' });
        if (supported) scheduleRetry();
      };
      handshake = setTimeout(unavailable, 3_000);
      try {
        runtime.sendMessage(config.EXTENSION_ID, { type: 'CAPTURE_CAPABILITIES' }, (reply) => {
          const error = runtime.lastError;
          if (disposed || current !== generation || !connecting) return;
          if (error) { unavailable(); return; }
          if (!isMessage(reply) || reply.protocol !== 1 || typeof reply.shortcut !== 'string') {
            clearTimeout(handshake);
            connecting = false;
            setStatus({ state: 'outdated', shortcut: null });
            return;
          }
          supported = true;
          setStatus({ state: 'connecting', shortcut: null });
          try {
            const connection = openPort(config.EXTENSION_ID, { name: 'vidwiz-capture-v1' });
            port = connection;
            const seen = new Set<string>();
            connection.onDisconnect.addListener(() => { void runtime.lastError; if (port === connection) unavailable(); });
            connection.onMessage.addListener((message) => {
              if (disposed || port !== connection || !isMessage(message)) return;
              if (message?.type === 'READY' && message.protocol === 1 && typeof message.shortcut === 'string') {
                clearTimeout(handshake);
                connecting = false;
                connected = true;
                attempt = 0;
                setStatus({ state: 'connected', shortcut: message.shortcut || null });
              } else if (message?.type === 'CAPTURE' && connected && typeof message.id === 'string' && !seen.has(message.id)) {
                seen.add(message.id);
                if (seen.size > 64) seen.delete(seen.values().next().value!);
                const result = captureShortcutBlocked() ? Promise.resolve<CaptureOutcome>('ignored') : captureRef.current();
                void result.catch((): CaptureOutcome => 'failed').then(outcome => {
                  // A save may complete after navigation or disconnect. Never replay it.
                  if (disposed || port !== connection) return;
                  try { connection.postMessage({ type: 'CAPTURE_RESULT', id: message.id, outcome }); } catch { unavailable(); }
                });
              }
            });
          } catch { unavailable(); }
        });
      } catch { unavailable(); }
    };
    const refresh = () => {
      if (document.visibilityState === 'hidden') return;
      attempt = 0;
      // Reconnect on focus to refresh a remapped or removed shortcut as well.
      if (port && connected) {
        const previous = port;
        port = undefined;
        connected = false;
        previous.disconnect();
      }
      clearTimeout(retry);
      retry = undefined;
      connect();
    };
    connect();
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    const onKey = (event: KeyboardEvent) => {
      if (connected || event.defaultPrevented || event.isComposing || event.repeat
        || (event.code !== 'KeyS' && event.key.toLowerCase() !== 's')
        || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || captureShortcutBlocked()) return;
      event.preventDefault();
      void captureRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      disposed = true;
      generation++;
      clearTimeout(retry);
      clearTimeout(handshake);
      port?.disconnect();
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
      document.removeEventListener('keydown', onKey);
    };
  }, []);
  return status;
}
