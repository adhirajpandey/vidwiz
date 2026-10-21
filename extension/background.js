import { CONFIG } from "./config.js";
import { capture, formatClock, removeToken, setToken, webUrl } from "./api.js";

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

// Alt+S: capture the current moment without opening the popup.
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-moment") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  let video;
  try {
    video = await chrome.tabs.sendMessage(tab.id, { action: "getVideo" });
  } catch {
    return; // Not a YouTube page with the content script.
  }
  if (!video?.videoId) {
    toast(tab.id, "Open a YouTube video to capture a moment.", "error");
    return;
  }
  try {
    const result = await capture(video);
    const at = formatClock(video.seconds);
    toast(tab.id, result.merged ? `Added to your moment near ${at}` : `Moment saved at ${at}`, "success");
  } catch (error) {
    if (error.status === 401) {
      toast(tab.id, "Log in to VidWiz to capture moments.", "error");
      chrome.tabs.create({ url: webUrl("/login") });
    } else {
      toast(tab.id, error.message, "error");
    }
  }
});
