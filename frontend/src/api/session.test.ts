import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from './fetch';
import {
  SESSION_EXPIRED_EVENT,
  shouldNotifySessionExpired,
} from './session';

const storage = {
  getItem: vi.fn<(key: string) => string | null>(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(() => null),
  length: 0,
};

beforeEach(() => {
  vi.restoreAllMocks();
  storage.getItem.mockReset();
  storage.getItem.mockReturnValue(null);
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
    const headers = new Headers({ Authorization: 'Bearer token' });
    expect(shouldNotifySessionExpired('/auth/login', headers)).toBe(false);
    expect(shouldNotifySessionExpired('/auth/google', headers)).toBe(false);
    expect(shouldNotifySessionExpired('/auth/register', headers)).toBe(false);
  });

  it('only treats unauthorized JWT requests as expired sessions', () => {
    const jwtHeaders = new Headers({ Authorization: 'Bearer token' });
    const guestHeaders = new Headers({ 'X-Guest-Session-ID': 'guest-id' });

    expect(shouldNotifySessionExpired('/users/me', jwtHeaders)).toBe(true);
    expect(
      shouldNotifySessionExpired(
        'https://api.vidwiz.online/v2/conversations/12/messages',
        new Headers({
          Authorization: 'Bearer token',
          'X-Guest-Session-ID': 'guest-id',
        })
      )
    ).toBe(true);
    expect(shouldNotifySessionExpired('/users/me', guestHeaders)).toBe(false);
    expect(shouldNotifySessionExpired('/users/me', undefined)).toBe(false);
  });

  it('emits one session event for an unauthorized application fetch', async () => {
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 }));
    storage.getItem.mockImplementation((key) =>
      key === 'token' ? `header.${payload}.signature` : null
    );
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

  it('does not emit a session event for an unauthorized guest fetch', async () => {
    storage.getItem.mockImplementation((key) =>
      key === 'guestSessionId' ? 'guest-id' : null
    );
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 401 }))
    );
    let eventCount = 0;
    window.addEventListener(SESSION_EXPIRED_EVENT, () => {
      eventCount += 1;
    });

    await apiFetch('/conversations/12/messages');

    expect(eventCount).toBe(0);
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
