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

  function channel() {
    // Newer Shorts renderers omit is-active; the main Shorts player still
    // belongs to the current renderer, not its preloaded neighbours.
    const short = document.querySelector("ytd-reel-video-renderer[is-active]")
      || document.querySelector("#shorts-player")?.closest("ytd-reel-video-renderer");
    const owner = window.location.pathname.startsWith("/shorts/")
      ? short?.querySelector("#channel-name, .ytReelChannelBarViewModelChannelName")
      : document.querySelector("ytd-watch-metadata #owner #channel-name a, ytd-video-owner-renderer #channel-name");
    return owner?.innerText?.trim() || null;
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
    return { videoId: id, title: title(), channel: channel(), seconds: element.currentTime || 0, ad };
  }

  /**
   * The player the toast shows in, or null to use the window: the active
   * Short's player, or the main player in normal, theatre, and fullscreen mode.
   * The miniplayer is too small, so it uses the window too.
   */
  function toastPlayer() {
    const element = player()?.closest(".html5-video-player");
    if (!element || document.querySelector("ytd-app[miniplayer-is-active]")) return null;
    const { width, height } = element.getBoundingClientRect();
    return width >= 320 && height >= 180 ? element : null;
  }

  let toastHost = null;
  function showToast(text, kind) {
    if (!toastHost) {
      toastHost = document.createElement("div");
      toastHost.attachShadow({ mode: "open" });
    }
    // Inside the player, top right, where the user is looking. Otherwise the
    // window's bottom left, clear of YouTube's own notices; in fullscreen only
    // the fullscreen element's subtree is visible.
    const inPlayer = toastPlayer();
    const parent = inPlayer || document.fullscreenElement || document.documentElement;
    if (toastHost.parentNode !== parent) parent.appendChild(toastHost);
    // Shorts draw their own controls over the player's top corners, so there
    // the toast sits centred below that row.
    const shorts = inPlayer?.id === "shorts-player";
    const place = !inPlayer
      ? "position: fixed; bottom: 24px; left: 24px; max-width: calc(100vw - 48px);"
      : shorts
        ? "position: absolute; top: 64px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 32px);"
        : "position: absolute; top: 16px; right: 16px; max-width: calc(100% - 32px);";
    toastHost.style.cssText = `${place} z-index: 2147483647; pointer-events: none;`;
    const root = toastHost.shadowRoot;
    root.innerHTML = "";
    const style = document.createElement("style");
    // The web app's toast: navy card, green check for success, red for errors.
    style.textContent = `
      .toast { display: flex; align-items: center; gap: 10px; max-width: 360px; padding: 10px 16px 10px 12px; border-radius: 12px;
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
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = kind === "error" ? "!" : "✓";
    const label = document.createElement("span");
    label.textContent = text;
    toast.append(icon, label);
    root.append(style, toast);
    clearTimeout(showToast.timer);
    // Errors stay longer: they need reading, and the toast has no close button.
    showToast.timer = setTimeout(() => { root.innerHTML = ""; }, kind === "error" ? 6000 : 2600);
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
