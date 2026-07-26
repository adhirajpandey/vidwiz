import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from './fetch';
import {
  SESSION_EXPIRED_EVENT,
  shouldNotifySessionExpired,
} from './session';

const storage = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(() => null),
  length: 0,
};

beforeEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage,
  });
  Object.defineProperty(globalThis, 'sessionStorage', {
    configurable: true,
    value: storage,
  });
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: new EventTarget(),
  });
});

describe('shouldNotifySessionExpired', () => {
  it('keeps credential failures on authentication forms', () => {
    expect(shouldNotifySessionExpired('/auth/login')).toBe(false);
    expect(shouldNotifySessionExpired('/auth/google')).toBe(false);
    expect(shouldNotifySessionExpired('/auth/register')).toBe(false);
  });

  it('treats unauthorized application requests as expired sessions', () => {
    expect(shouldNotifySessionExpired('/users/me')).toBe(true);
    expect(
      shouldNotifySessionExpired(
        'https://api.vidwiz.online/v2/conversations/12/messages'
      )
    ).toBe(true);
  });

  it('emits one session event for an unauthorized application fetch', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, {
        status: 401,
        headers: { 'X-Request-ID': 'request-401' },
      }))
    );
    const details: unknown[] = [];
    window.addEventListener(SESSION_EXPIRED_EVENT, (event) => {
      details.push((event as CustomEvent).detail);
    });

    await apiFetch('/users/me');

    expect(details).toStrictEqual([{ requestId: 'request-401' }]);
  });

  it('does not emit a session event for rejected login credentials', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 401 }))
    );
    let eventCount = 0;
    window.addEventListener(SESSION_EXPIRED_EVENT, () => {
      eventCount += 1;
    });

    await apiFetch('/auth/login', { method: 'POST' });

    expect(eventCount).toBe(0);
  });

  it('refuses to attach authentication headers to external URLs', async () => {
    await expect(
      apiFetch('https://example.com/collect')
    ).rejects.toThrow('API requests must target the configured VidWiz API');
  });
});
