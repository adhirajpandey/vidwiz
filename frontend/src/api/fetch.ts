import config from '../config';
import { getAuthHeaders } from '../lib/authUtils';
import {
  markSessionExpiredHandled,
  notifySessionExpired,
  shouldNotifySessionExpired,
} from './session';

/** A non-2xx API response with its parsed JSON body, if any. */
export class ApiError extends Error {
  readonly response: Response;
  readonly data: unknown;

  constructor(response: Response, data: unknown) {
    super(`Request failed with status ${response.status}`);
    this.name = 'ApiError';
    this.response = response;
    this.data = data;
  }
}

type QueryParams = Record<string, string | number | undefined>;

function apiUrl(input: string): string {
  if (/^https?:\/\//i.test(input)) {
    if (
      input !== config.API_URL &&
      !input.startsWith(`${config.API_URL}/`)
    ) {
      throw new Error('API requests must target the configured VidWiz API');
    }
    return input;
  }
  return `${config.API_URL}${input.startsWith('/') ? input : `/${input}`}`;
}

function guestSessionId(): string | null {
  try {
    return sessionStorage.getItem('guestSessionId');
  } catch {
    return null;
  }
}

export async function apiFetch(
  input: string,
  init: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(getAuthHeaders());
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));

  const guestId = guestSessionId();
  if (guestId) headers.set('X-Guest-Session-ID', guestId);

  const response = await fetch(apiUrl(input), {
    ...init,
    headers,
  });

  if (
    response.status === 401 &&
    shouldNotifySessionExpired(input, headers)
  ) {
    markSessionExpiredHandled(response);
    notifySessionExpired({
      requestId: response.headers.get('X-Request-ID') ?? undefined,
    });
  }

  return response;
}

/** Sends a JSON request and returns the parsed body; throws `ApiError` on non-2xx. */
export async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  { body, params }: { body?: unknown; params?: QueryParams } = {}
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) query.set(key, String(value));
  }
  const search = query.size ? `?${query}` : '';
  const response = await apiFetch(`${path}${search}`, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = undefined;
  }
  if (!response.ok) throw new ApiError(response, data);
  return data as T;
}
