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

function fetchVideoTitle() {
  if (window.location.hostname.includes("youtube.com") && window.location.pathname === "/watch") {
    const el = document.querySelector(".title.style-scope.ytd-video-primary-info-renderer")
    return el ? el.textContent.trim() : "No YouTube video title found."
  }
  return "No YouTube video found."
}

function fetchVideoTimestamp() {
  if (window.location.hostname.includes("youtube.com") && window.location.pathname === "/watch") {
    const el = document.querySelector(".ytp-time-current")
    return el ? el.textContent.trim() : null
  }
  return null
}

function fetchVideoDuration() {
  if (window.location.hostname.includes("youtube.com") && window.location.pathname === "/watch") {
    const el = document.querySelector(".ytp-time-duration")
    return el ? el.textContent.trim() : null
  }
  return null
}
