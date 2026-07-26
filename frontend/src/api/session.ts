export const SESSION_EXPIRED_EVENT = 'vidwiz:session-expired';

export interface SessionExpiredDetail {
  requestId?: string;
}

const AUTH_ATTEMPT_PATTERN = /\/auth\/(?:login|register|google)(?:$|[?#])/;
const handledSessionErrors = new WeakSet<object>();

export function shouldNotifySessionExpired(url: string | undefined): boolean {
  return !url || !AUTH_ATTEMPT_PATTERN.test(url);
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
