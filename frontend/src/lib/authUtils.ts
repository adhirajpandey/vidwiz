/**
 * Authentication utility functions
 * Centralized token management with expiration validation
 */

export interface TokenPayload {
  user_id: number;
  email?: string;
  name?: string;
  profile_image_url?: string;
  exp?: number;
  iat?: number;
  type?: string;
}

/**
 * Decodes a JWT token without verification
 * Returns null if token is invalid or malformed
 */
export function decodeToken(token: string): TokenPayload | null {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) {
      return null;
    }
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Failed to decode JWT', error);
    return null;
  }
}

/**
 * Checks if a token is expired
 * Returns true if token is expired or invalid
 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) {
    return true;
  }

  const payload = decodeToken(token);
  if (!payload || !payload.exp) {
    return true;
  }

  // exp is in seconds, Date.now() is in milliseconds
  const expirationTime = payload.exp * 1000;
  const currentTime = Date.now();

  // Add 5 second buffer to account for clock skew
  return currentTime >= expirationTime - 5000;
}

/**
 * Gets the token from localStorage
 * Returns null if token doesn't exist or is expired
 * Automatically removes expired tokens
 */
export function getToken(): string | null {
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      return null;
    }

    // Check if token is expired
    if (isTokenExpired(token)) {
      // Remove expired token
      localStorage.removeItem('token');
      return null;
    }

    return token;
  } catch (error) {
    console.error('Error getting token from localStorage', error);
    return null;
  }
}

/**
 * Checks if user is authenticated (has valid, non-expired token)
 */
export function isAuthenticated(): boolean {
  return getToken() !== null;
}

/**
 * Gets the decoded token payload
 * Returns null if token is invalid or expired
 */
export function getTokenPayload(): TokenPayload | null {
  const token = getToken();
  if (!token) {
    return null;
  }
  return decodeToken(token);
}

/**
 * Gets user info from token
 * Returns null if token is invalid or expired
 */
export function getUserFromToken(): { email?: string; name?: string; profile_image_url?: string } | null {
  const payload = getTokenPayload();
  if (!payload) {
    return null;
  }
  return {
    email: payload.email,
    name: payload.name,
    profile_image_url: payload.profile_image_url,
  };
}

/**
 * Removes token from localStorage
 */
export function removeToken(): void {
  try {
    localStorage.removeItem('token');
  } catch (error) {
    console.error('Error removing token from localStorage', error);
  }
}

/**
 * Sets token in localStorage
 * Does not validate the token format
 */
export function setToken(token: string): void {
  try {
    localStorage.setItem('token', token);
  } catch (error) {
    console.error('Error setting token in localStorage', error);
  }
}

/**
 * Gets authorization headers for API requests
 * Returns headers with Bearer token if valid token exists
 * Returns empty headers if no valid token
 */
export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Validates token before making API calls
 * Returns the token if valid, null if expired/invalid
 * Automatically cleans up expired tokens
 */
export function validateTokenForRequest(): string | null {
  return getToken();
}
