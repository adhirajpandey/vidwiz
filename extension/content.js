const CONSTANTS = {
  SELECTORS: {
    TITLE_PRIMARY: ".title.style-scope.ytd-video-primary-info-renderer",
    TITLE_META: 'meta[name="title"]',
    VIDEO: "video"
  },
  URL: {
    HOSTNAME_PART: "youtube.com",
    WATCH_PATH: "/watch"
  },
  STRINGS: {
    TITLE_SUFFIX: " - YouTube",
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
    const el = document.querySelector(CONSTANTS.SELECTORS.TITLE_PRIMARY)
    if (el) return el.textContent.trim()
    
    // Fallback: meta tag
    const meta = document.querySelector(CONSTANTS.SELECTORS.TITLE_META)
    if (meta) return meta.content

    // Fallback: document title (often formatted as "Video Title - YouTube")
    return document.title.replace(CONSTANTS.STRINGS.TITLE_SUFFIX, "")
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
