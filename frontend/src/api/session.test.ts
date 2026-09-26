import { beforeEach, describe, expect, it, vi } from 'vitest';
import { normalizeApiError } from './errors';
import { ApiError, apiFetch, apiRequest } from './fetch';
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

describe('apiRequest', () => {
  it('sends JSON, drops undefined query values, and parses the response', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      apiRequest('POST', '/videos', { body: { a: 1 }, params: { q: '', page: 2, sort: undefined } })
    ).resolves.toStrictEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/videos\?q=&page=2$/);
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"a":1}');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
  });

  it('returns undefined for an empty success body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));

    await expect(apiRequest('DELETE', '/notes/1')).resolves.toBeUndefined();
  });

  it('throws an ApiError with the parsed error body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ error: { message: 'Nope' } }), { status: 409 }))
    );

    const error = await apiRequest('GET', '/users/me').catch((cause: unknown) => cause);
    expect(error).toBeInstanceOf(ApiError);
    expect(normalizeApiError(error, 'Failed')).toMatchObject({ status: 409, message: 'Nope', kind: 'conflict' });
  });

  it('marks unauthorized application requests as centrally handled', async () => {
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 }));
    storage.getItem.mockImplementation((key) =>
      key === 'token' ? `header.${payload}.signature` : null
    );
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 401 })));

    const error = await apiRequest('GET', '/users/me').catch((cause: unknown) => cause);
    expect(normalizeApiError(error, 'Failed').handled).toBe(true);
  });
});

