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
    // The web app's toast: navy card, green check for success, red for errors.
    // In fullscreen it sits above YouTube's progress bar and controls.
    style.textContent = `
      .toast { position: fixed; bottom: ${document.fullscreenElement ? 96 : 24}px; left: 50%; transform: translateX(-50%);
        z-index: 2147483647; display: flex; align-items: center; gap: 10px; padding: 10px 16px 10px 12px; border-radius: 12px;
        font: 500 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; color: hsl(233 31% 94%); background: hsl(233 29% 18%);
        box-shadow: 0 10px 28px rgb(0 0 0 / 35%); border: 1px solid hsl(234 24% 23%); }
      .icon { width: 20px; height: 20px; border-radius: 50%; flex: none; display: grid; place-items: center;
        background: hsl(152 45% 58%); color: hsl(234 33% 12%); font-size: 12px; font-weight: 800; }
      .error .icon { background: hsl(0 75% 66%); }`;
    const toast = document.createElement("div");
    toast.className = `toast ${kind === "error" ? "error" : ""}`;
    toast.setAttribute("role", "status");
    const icon = document.createElement("span");
    icon.className = "icon";
    icon.textContent = kind === "error" ? "!" : "✓";
    const label = document.createElement("span");
    label.textContent = text;
    toast.append(icon, label);
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
