/**
 * Token storage with expiration checks and extension auth sync.
 */
import config from '../config';

const TOKEN_KEY = 'token';

interface TokenPayload {
  user_id: number;
  email?: string;
  name?: string;
  profile_image_url?: string;
  exp?: number;
}

/** Decodes a JWT payload without verification; returns null when malformed. */
function decodeToken(token: string): TokenPayload | null {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch (error) {
    console.error('Failed to decode JWT', error);
    return null;
  }
}

/** Sends a login or logout message to the browser extension, if installed. */
function syncExtension(message: { type: 'SYNC_TOKEN'; token: string } | { type: 'LOGOUT' }): void {
  const runtime = typeof chrome !== 'undefined' ? chrome.runtime : undefined;
  if (!runtime?.sendMessage) return;
  runtime.sendMessage(config.EXTENSION_ID, message, () => {
    if (runtime.lastError) {
      // Extension not installed or not listening.
      console.debug(`Extension not reachable for ${message.type}:`, runtime.lastError.message);
    }
  });
}

/** Returns the stored token, removing it when it is expired or malformed. */
export function getToken(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const exp = decodeToken(token)?.exp;
    // Allow 5 seconds of clock skew.
    if (!exp || Date.now() >= exp * 1000 - 5000) {
      removeToken();
      return null;
    }
    return token;
  } catch (error) {
    console.error('Error getting token from localStorage', error);
    return null;
  }
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export function getUserFromToken(): Pick<TokenPayload, 'email' | 'name' | 'profile_image_url'> | null {
  const token = getToken();
  const payload = token ? decodeToken(token) : null;
  if (!payload) return null;
  return { email: payload.email, name: payload.name, profile_image_url: payload.profile_image_url };
}

export function removeToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    syncExtension({ type: 'LOGOUT' });
  } catch (error) {
    console.error('Error removing token from localStorage', error);
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    syncExtension({ type: 'SYNC_TOKEN', token });
  } catch (error) {
    console.error('Error setting token in localStorage', error);
  }
}

/** JSON headers with a Bearer token when a valid token exists. */
export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}
