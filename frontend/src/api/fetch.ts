import config from '../config';
import { getAuthHeaders } from '../lib/authUtils';
import {
  notifySessionExpired,
  shouldNotifySessionExpired,
} from './session';

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
    shouldNotifySessionExpired(input)
  ) {
    notifySessionExpired({
      requestId: response.headers.get('X-Request-ID') ?? undefined,
    });
  }

  return response;
}
