export const SESSION_EXPIRED_EVENT = 'vidwiz:session-expired';

export interface SessionExpiredDetail {
  requestId?: string;
}

const AUTH_ATTEMPT_PATTERN = /\/auth\/(?:login|register|google)(?:$|[?#])/;
const handledSessionErrors = new WeakSet<object>();

function headerValue(headers: unknown, name: string): string | undefined {
  if (!headers || typeof headers !== 'object') return undefined;

  const getter = (headers as { get?: unknown }).get;
  if (typeof getter === 'function') {
    const value = getter.call(headers, name);
    return typeof value === 'string' ? value : undefined;
  }

  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === name.toLowerCase()) {
      return typeof value === 'string' ? value : undefined;
    }
  }
  return undefined;
}

export function shouldNotifySessionExpired(
  url: string | undefined,
  headers: unknown
): boolean {
  const authorization = headerValue(headers, 'Authorization');
  return (
    Boolean(authorization && /^Bearer\s+\S+$/i.test(authorization.trim())) &&
    (!url || !AUTH_ATTEMPT_PATTERN.test(url))
  );
}

export function notifySessionExpired(detail: SessionExpiredDetail = {}): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<SessionExpiredDetail>(SESSION_EXPIRED_EVENT, { detail })
  );
}

export function markSessionExpiredHandled(cause: object): void {
  handledSessionErrors.add(cause);
}

export function wasSessionExpiredHandled(cause: unknown): boolean {
  return typeof cause === 'object' &&
    cause !== null &&
    handledSessionErrors.has(cause);
}
