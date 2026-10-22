// Shared by the popup and the background worker: token storage and API calls.
import { CONFIG } from "./config.js";

const TOKEN_KEY = "token";

/** Reads `exp` from a JWT payload without verification; null when malformed. */
function tokenExpiry(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64)).exp || null;
  } catch {
    return null;
  }
}

/** The synced web session token, or null when missing or expired. */
export async function getToken() {
  const token = (await chrome.storage.local.get(TOKEN_KEY))[TOKEN_KEY];
  if (!token) return null;
  const exp = tokenExpiry(token);
  // Allow 5 seconds of clock skew.
  if (!exp || Date.now() >= exp * 1000 - 5000) {
    await clearToken(token);
    return null;
  }
  return token;
}

/** Removes the token only if it is still `token`, so a newer synced one survives. */
export async function clearToken(token) {
  const current = (await chrome.storage.local.get(TOKEN_KEY))[TOKEN_KEY];
  if (current === token) await chrome.storage.local.remove(TOKEN_KEY);
}

export async function setToken(token) {
  await chrome.storage.local.set({ [TOKEN_KEY]: token });
}

export async function removeToken() {
  await chrome.storage.local.remove(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const FALLBACK = {
  0: "Can't reach VidWiz. Check your connection and try again.",
  401: "Your session expired. Log in to VidWiz again.",
  429: "Too many requests. Wait a moment and try again.",
  500: "VidWiz had a problem. Try again shortly.",
};

/** JSON request with the session token. Errors carry a user-facing message. */
export async function api(path, { method = "GET", body } = {}) {
  const token = await getToken();
  if (!token) throw new ApiError(401, FALLBACK[401]);
  let response;
  try {
    response = await fetch(`${CONFIG.API_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, FALLBACK[0]);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) await clearToken(token);
    // API errors look like { error: { message, details } }.
    const details = data?.error?.details;
    const message = response.status === 422 && Array.isArray(details) && details.length
      ? details.map((detail) => detail.message).join("; ")
      : data?.error?.message || FALLBACK[response.status] || FALLBACK[500];
    throw new ApiError(response.status, message);
  }
  return data;
}

export function capture({ videoId, title, seconds, note, ai }) {
  return api("/captures", {
    method: "POST",
    body: {
      video: videoId,
      title: title || undefined,
      at: Math.max(0, Math.floor(seconds)),
      note: note || null,
      ...(ai === undefined ? {} : { ai }),
      source: "extension",
    },
  });
}

export function formatClock(seconds) {
  const whole = Math.max(0, Math.floor(seconds));
  const h = Math.floor(whole / 3600);
  const m = Math.floor(whole / 60) % 60;
  const s = String(whole % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

export const webUrl = (path) => `${CONFIG.WEB_URL}${path}`;

// Same lead-in as the web app: its 3 seconds plus the 2 its player adds.
const MOMENT_LEAD_SECONDS = 5;

/** Where playing a moment starts: a few seconds before it was saved. */
export function playFrom(moment) {
  return Math.max(0, moment.at_seconds - MOMENT_LEAD_SECONDS);
}

/** True for YouTube watch and Shorts URLs, which the content script reads. */
export function isVideoUrl(url) {
  try {
    const { hostname, pathname, searchParams } = new URL(url);
    if (hostname !== "youtube.com" && !hostname.endsWith(".youtube.com")) return false;
    return (pathname === "/watch" && searchParams.has("v")) || pathname.startsWith("/shorts/");
  } catch {
    return false;
  }
}

export const MESSAGES = {
  ad: "An ad is playing. Save the moment after it ends.",
  reload: "Reload this YouTube tab to use VidWiz.",
};
