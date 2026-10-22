import { ApiError, MESSAGES, api, capture, formatClock, getToken, isVideoUrl, playFrom, webUrl } from "./api.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["login-view", "idle-view", "reload-view", "capture-view"];
const show = (id) => {
  for (const view of VIEWS) $(view).classList.toggle("hidden", view !== id);
};
const openTab = (path) => chrome.tabs.create({ url: webUrl(path) });
const onClick = (id, handler) => $(id).addEventListener("click", (event) => { event.preventDefault(); handler(); });

function feedback(text, kind = "") {
  const element = $("feedback");
  element.textContent = text;
  element.className = `feedback ${kind}`;
}

function showLogin(reason) {
  if (reason) $("login-reason").textContent = reason;
  show("login-view");
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function currentVideo(tab) {
  try {
    return await chrome.tabs.sendMessage(tab.id, { action: "getVideo" });
  } catch {
    return null; // The page loaded before the extension; a reload fixes it.
  }
}

// The status line under a moment while its AI line is pending or didn't happen,
// in the web app's words.
const STATUS = {
  queued: { text: "Writing the AI line…", pending: true },
  waiting_transcript: { text: "AI line waits for the transcript", pending: true },
  no_transcript: { text: "This video has no transcript, so there is no AI line or quote" },
  insufficient_credits: { text: "Not enough credits for the AI line.", link: { text: "Get credits", path: "/settings#credits" } },
  failed: { text: "The AI line failed.", link: { text: "Retry in VidWiz", path: null } },
};

const isPending = (moment) => Boolean(STATUS[moment.ai_status]?.pending);

/** The web app's AI line mark. */
function sparkle() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "13");
  svg.setAttribute("height", "13");
  svg.setAttribute("aria-label", "AI line");
  svg.innerHTML = '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>';
  return svg;
}

function momentRow(tab, moment) {
  const start = playFrom(moment);
  const item = document.createElement("li");
  const time = document.createElement("button");
  time.className = "time tabular";
  time.textContent = formatClock(moment.at_seconds);
  time.setAttribute("aria-label", `Play from ${formatClock(start)}`);
  time.addEventListener("click", () => chrome.tabs.sendMessage(tab.id, { action: "seek", seconds: start }).catch(() => {}));

  const body = document.createElement("div");
  body.className = "moment-body";
  const add = (className, text) => {
    const element = document.createElement("p");
    element.className = `moment-text ${className}`;
    element.textContent = text;
    body.append(element);
    return element;
  };
  // Like the web app: the AI line and note lead, and the quote shows only without them.
  if (moment.ai_text) add("ai", moment.ai_text).prepend(sparkle());
  if (moment.note) add("note", moment.note);
  const status = moment.ai_text ? null : STATUS[moment.ai_status];
  if (status) {
    const line = document.createElement("p");
    line.className = "moment-status";
    line.textContent = status.text;
    if (status.link) {
      const link = document.createElement("a");
      link.href = "#";
      link.textContent = status.link.text;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        openTab(status.link.path ?? `/v/${moment.video_id}`);
      });
      line.append(" ", link);
    }
    body.append(line);
  }
  if (!moment.ai_text && !moment.note) {
    if (moment.quote) add("quote", moment.quote);
    else if (!status) add("pending", "Saved moment");
  }
  item.append(time, body);
  return item;
}

// While an AI line is on its way, refresh the list like the web app does.
const POLL_MS = 3000;
const POLL_LIMIT_MS = 3 * 60 * 1000;
let pollTimer = null;
let pollUntil = 0;

async function renderMoments(tab, videoId) {
  clearTimeout(pollTimer);
  const list = $("moments");
  let moments;
  try {
    moments = await api(`/videos/${videoId}/moments`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showLogin(error.message);
      return;
    }
    const failed = document.createElement("li");
    failed.className = "muted";
    failed.textContent = "Couldn't load this video's moments.";
    list.replaceChildren(failed);
    return;
  }
  list.replaceChildren(...moments.map((moment) => momentRow(tab, moment)));
  if (!moments.length) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "No moments yet.";
    list.append(empty);
  }
  if (moments.some(isPending) && Date.now() < pollUntil) {
    pollTimer = setTimeout(() => void renderMoments(tab, videoId), POLL_MS);
  }
}

function refreshMoments(tab, videoId) {
  pollUntil = Date.now() + POLL_LIMIT_MS;
  void renderMoments(tab, videoId);
}

async function shortcutLabel() {
  const commands = await chrome.commands.getAll();
  return commands.find((command) => command.name === "capture-moment")?.shortcut || "Alt+S";
}

/** The save options menu beside Save moment, as in the web app. */
function setupMenu(aiDefault, save) {
  const toggle = $("capture-toggle");
  const menu = $("capture-menu");
  const options = [...menu.querySelectorAll(".option")];
  for (const option of options) {
    const isDefault = (option.dataset.ai === "true") === aiDefault;
    option.setAttribute("aria-checked", String(isDefault));
    option.title = isDefault ? "Your default" : "Saves this moment only";
    option.addEventListener("click", () => {
      close();
      void save(option.dataset.ai === "true");
    });
  }
  $("capture").title = aiDefault ? "Saves with an AI line, 1 credit" : "Saves without an AI line";

  function open() {
    menu.classList.remove("hidden");
    toggle.setAttribute("aria-expanded", "true");
    options[0].focus();
  }
  function close() {
    menu.classList.add("hidden");
    toggle.setAttribute("aria-expanded", "false");
  }
  toggle.addEventListener("click", () => (menu.classList.contains("hidden") ? open() : close()));
  menu.addEventListener("keydown", (event) => {
    const items = [...options, $("change-default")];
    const index = items.indexOf(document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      toggle.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      items[(index + step + items.length) % items.length].focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target) && !toggle.contains(event.target)) close();
  });
  onClick("change-default", () => openTab("/settings#account"));
  toggle.classList.remove("hidden");
}

async function init() {
  onClick("open-app", () => openTab("/"));
  $("login").addEventListener("click", () => openTab("/login"));
  $("shortcut").textContent = await shortcutLabel();

  if (!(await getToken())) {
    showLogin();
    return;
  }
  const tab = await activeTab();
  if (!tab?.id || !isVideoUrl(tab.url)) {
    show("idle-view");
    return;
  }
  const video = await currentVideo(tab);
  if (!video) {
    $("reload").addEventListener("click", () => {
      chrome.tabs.reload(tab.id);
      window.close();
    });
    show("reload-view");
    return;
  }

  const buttons = () => [$("capture"), $("capture-toggle"), ...document.querySelectorAll("#capture-menu .option")];
  let saving = false;
  let ad = video.ad;
  const setDisabled = () => {
    for (const button of buttons()) button.disabled = saving || ad;
  };

  /** `ai` undefined lets the server apply the user's default. */
  async function save(ai) {
    if (saving || ad) return;
    saving = true;
    setDisabled();
    // Save where the video is now, not where it was when the popup opened.
    const latest = (await currentVideo(tab)) || video;
    try {
      if (latest.ad) {
        feedback(MESSAGES.ad, "error");
        return;
      }
      const result = await capture({ ...latest, note: $("note").value.trim(), ai });
      $("note").value = "";
      feedback(result.merged ? "Added to a nearby moment." : `Saved at ${formatClock(latest.seconds)}.`, "success");
      refreshMoments(tab, video.videoId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        showLogin(error.message);
      } else {
        feedback(error.message, "error");
      }
    } finally {
      saving = false;
      setDisabled();
    }
  }

  // Keep the button's time and the ad state in step with the playing video.
  function showPlayhead(current) {
    $("capture-time").textContent = `at ${formatClock(current.seconds)}`;
    if (current.ad !== ad) {
      ad = current.ad;
      setDisabled();
      feedback(ad ? MESSAGES.ad : "");
    }
  }

  show("capture-view");
  $("video-title").textContent = video.title;
  $("capture-time").textContent = `at ${formatClock(video.seconds)}`;
  if (ad) feedback(MESSAGES.ad);
  setDisabled();
  setInterval(async () => {
    const current = await currentVideo(tab);
    if (current?.videoId === video.videoId) showPlayhead(current);
  }, 500);
  onClick("open-video", () => openTab(`/v/${video.videoId}`));

  try {
    const profile = await api("/users/me");
    setupMenu(Boolean(profile.ai_moments_default), save);
    setDisabled();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showLogin(error.message);
      return;
    }
    // Without the profile, Save moment still works with the server's default.
  }
  refreshMoments(tab, video.videoId);
  $("note").focus();

  $("capture-form").addEventListener("submit", (event) => {
    event.preventDefault();
    void save(undefined);
  });
  $("note").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("capture-form").requestSubmit();
    }
  });
}

void init();
