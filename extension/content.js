const CONSTANTS = {
  SELECTORS: {
    // Current watch-page title; YouTube updates it on in-page navigation.
    TITLE_PRIMARY: "ytd-watch-metadata h1",
    VIDEO: "video"
  },
  URL: {
    HOSTNAME_PART: "youtube.com",
    WATCH_PATH: "/watch"
  },
  STRINGS: {
    TITLE_SUFFIX: " - YouTube",
    // Unread notification count YouTube prepends to the tab title, e.g. "(3) ".
    TITLE_COUNT_PREFIX: /^\(\d+\)\s*/,
    NO_VIDEO_FOUND: "No YouTube video found."
  }
};

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getVideoData") {
    sendResponse({
      title: fetchVideoTitle(),
      timestamp: fetchVideoTimestamp(),
      duration: fetchVideoDuration()
    });
  } else if (request.action === "getVideoTimestamp") {
    sendResponse(fetchVideoTimestamp());
  }
});

function isYouTubeWatchPage() {
  return window.location.hostname.includes(CONSTANTS.URL.HOSTNAME_PART) && 
         window.location.pathname === CONSTANTS.URL.WATCH_PATH;
}

function fetchVideoTitle() {
  if (isYouTubeWatchPage()) {
    // Try primary title element
    const title = document.querySelector(CONSTANTS.SELECTORS.TITLE_PRIMARY)?.textContent.trim()
    if (title) return title

    // Fallback: document title, formatted as "(3) Video Title - YouTube".
    // The meta title tag is not used because it keeps the first video's title after in-page navigation.
    return document.title
      .replace(CONSTANTS.STRINGS.TITLE_COUNT_PREFIX, "")
      .replace(CONSTANTS.STRINGS.TITLE_SUFFIX, "")
      .trim()
  }
  return CONSTANTS.STRINGS.NO_VIDEO_FOUND
}

function fetchVideoTimestamp() {
  if (isYouTubeWatchPage()) {
    const video = document.querySelector(CONSTANTS.SELECTORS.VIDEO)
    if (video) {
        return formatTime(video.currentTime)
    }
  }
  return null
}

function fetchVideoDuration() {
  if (isYouTubeWatchPage()) {
    const video = document.querySelector(CONSTANTS.SELECTORS.VIDEO)
    if (video) {
        return formatTime(video.duration)
    }
  }
  return null
}

function formatTime(seconds) {
    if (isNaN(seconds)) return null
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    return `${m}:${s.toString().padStart(2, '0')}`
}
