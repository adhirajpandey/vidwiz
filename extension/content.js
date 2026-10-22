// Reads the current YouTube video and shows capture feedback on the page.
(() => {
  const VIDEO_ID = /^[a-zA-Z0-9_-]{11}$/;

  function videoId() {
    const url = new URL(window.location.href);
    if (url.pathname === "/watch") return url.searchParams.get("v");
    const shorts = url.pathname.match(/^\/shorts\/([^/?#]+)/);
    return shorts ? shorts[1] : null;
  }

  function title() {
    // The watch-page heading updates on in-page navigation; the meta title does not.
    const heading = document.querySelector("ytd-watch-metadata h1, ytd-reel-video-renderer[is-active] h2")?.textContent?.trim();
    if (heading) return heading;
    return document.title.replace(/^\(\d+\)\s*/, "").replace(/\s+-\s+YouTube$/, "").trim();
  }

  function player() {
    // Shorts keep several players; the playing one is the visible, active one.
    // On watch pages, feed previews and the miniplayer add other <video> elements,
    // so prefer the main player's.
    if (window.location.pathname.startsWith("/shorts/")) {
      return document.querySelector("ytd-reel-video-renderer[is-active] video, #shorts-player video") || document.querySelector("video");
    }
    return document.querySelector("#movie_player video.html5-main-video") || document.querySelector("video.html5-main-video") || document.querySelector("video");
  }

  function currentVideo() {
    const id = videoId();
    const element = player();
    if (!id || !VIDEO_ID.test(id) || !element) return null;
    // During an ad, the element plays the ad, so its time isn't the video's.
    const ad = Boolean(element.closest(".html5-video-player")?.classList.contains("ad-showing"));
    return { videoId: id, title: title(), seconds: element.currentTime || 0, ad };
  }

  let toastHost = null;
  function showToast(text, kind) {
    if (!toastHost) {
      toastHost = document.createElement("div");
      toastHost.attachShadow({ mode: "open" });
    }
    // Only the fullscreen element's subtree is visible in fullscreen.
    const parent = document.fullscreenElement || document.documentElement;
    if (toastHost.parentNode !== parent) parent.appendChild(toastHost);
    const root = toastHost.shadowRoot;
    root.innerHTML = "";
    const style = document.createElement("style");
    style.textContent = `
      .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); z-index: 2147483647;
        display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 10px;
        font: 500 13px/1.4 system-ui, -apple-system, sans-serif; color: #fff; background: #18181b;
        box-shadow: 0 8px 24px rgb(0 0 0 / 30%); border: 1px solid rgb(255 255 255 / 10%); }
      .dot { width: 8px; height: 8px; border-radius: 50%; background: #a78bfa; flex: none; }
      .error .dot { background: #f87171; }`;
    const toast = document.createElement("div");
    toast.className = `toast ${kind === "error" ? "error" : ""}`;
    toast.setAttribute("role", "status");
    const dot = document.createElement("span");
    dot.className = "dot";
    const label = document.createElement("span");
    label.textContent = text;
    toast.append(dot, label);
    root.append(style, toast);
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { root.innerHTML = ""; }, 2600);
  }

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "getVideo") {
      sendResponse(currentVideo());
    } else if (request.action === "seek") {
      const element = player();
      if (element && Number.isFinite(request.seconds)) {
        element.currentTime = Math.max(0, request.seconds);
        element.play().catch(() => {});
      }
      sendResponse(Boolean(element));
    } else if (request.action === "toast") {
      showToast(request.text, request.kind);
      sendResponse(true);
    }
  });
})();
