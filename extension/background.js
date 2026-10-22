import { CONFIG } from "./config.js";
import { MESSAGES, capture, formatClock, isVideoUrl, removeToken, setToken, webUrl } from "./api.js";

// Open the web app on first install so it syncs an existing login.
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === chrome.runtime.OnInstalledReason.INSTALL) {
    chrome.tabs.create({ url: webUrl("/") });
  }
});

// Login and logout from the web app (externally_connectable).
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  // externally_connectable already restricts senders; also require an exact origin.
  if (sender.origin !== CONFIG.WEB_URL) return false;
  if (message.type === "SYNC_TOKEN" && message.token) {
    setToken(message.token).then(() => sendResponse({ success: true }));
  } else if (message.type === "LOGOUT") {
    removeToken().then(() => sendResponse({ success: true }));
  } else {
    sendResponse({ success: false, error: "Unknown message type" });
  }
  return true;
});

function toast(tabId, text, kind) {
  chrome.tabs.sendMessage(tabId, { action: "toast", text, kind }).catch(() => {});
}

// A tab opened before the extension was installed or updated has no content
// script, so it can't show a toast; the badge asks for a reload instead.
function flagReload(tabId) {
  chrome.action.setBadgeText({ tabId, text: "!" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#dc2626" });
  chrome.action.setTitle({ tabId, title: MESSAGES.reload });
}

chrome.tabs.onUpdated.addListener((tabId, { status }) => {
  if (status !== "loading") return;
  chrome.action.setBadgeText({ tabId, text: "" });
  chrome.action.setTitle({ tabId, title: "VidWiz" });
});

const LOGIN_OPENED_KEY = "loginOpenedAt";

/** Opens the web login page, at most once a minute so repeated Alt+S presses don't stack tabs. */
async function openLogin() {
  const openedAt = (await chrome.storage.session.get(LOGIN_OPENED_KEY))[LOGIN_OPENED_KEY] || 0;
  if (Date.now() - openedAt < 60_000) return;
  await chrome.storage.session.set({ [LOGIN_OPENED_KEY]: Date.now() });
  await chrome.tabs.create({ url: webUrl("/login") });
}

// Alt+S: capture the current moment without opening the popup.
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-moment") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  let video;
  try {
    video = await chrome.tabs.sendMessage(tab.id, { action: "getVideo" });
  } catch {
    if (isVideoUrl(tab.url)) flagReload(tab.id);
    return; // Otherwise not a YouTube page.
  }
  if (!video?.videoId) {
    toast(tab.id, "Open a YouTube video to capture a moment.", "error");
    return;
  }
  if (video.ad) {
    toast(tab.id, MESSAGES.ad, "error");
    return;
  }
  try {
    const result = await capture(video);
    const at = formatClock(video.seconds);
    toast(tab.id, result.merged ? `Added to your moment near ${at}` : `Moment saved at ${at}`, "success");
  } catch (error) {
    if (error.status === 401) {
      toast(tab.id, "Log in to VidWiz to capture moments.", "error");
      await openLogin();
    } else {
      toast(tab.id, error.message, "error");
    }
  }
});
