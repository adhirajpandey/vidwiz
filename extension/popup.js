import { ApiError, MESSAGES, api, capture, formatClock, getToken, isVideoUrl, playFrom, webUrl } from "./api.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["login-view", "idle-view", "reload-view", "capture-view"];
const show = (id) => {
  for (const view of VIEWS) $(view).classList.toggle("hidden", view !== id);
  // The video view has its own "Open in VidWiz" for this video.
  $("open-app").classList.toggle("hidden", id === "capture-view");
};
const openTab = (path) => chrome.tabs.create({ url: webUrl(path) });
const onClick = (id, handler) => $(id).addEventListener("click", (event) => { event.preventDefault(); handler(); });

// A confirmation fades after a few seconds; errors stay until the next save.
const CONFIRMATION_MS = 3000;
let feedbackTimer = null;

function feedback(text, kind = "") {
  const element = $("feedback");
  clearTimeout(feedbackTimer);
  element.textContent = text;
  element.className = `feedback ${kind}`;
  if (text && kind === "success") {
    const icon = document.createElement("span");
    icon.className = "feedback-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "✓";
    element.prepend(icon);
    feedbackTimer = setTimeout(() => {
      element.classList.add("leaving");
      feedbackTimer = setTimeout(() => feedback(""), 250);
    }, CONFIRMATION_MS);
  }
}

/** The web app's coin mark for credits. */
function coin() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = '<g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/></g>';
  return svg;
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
  insufficient_credits: { text: "Not enough credits for the AI line.", link: { text: "Get credits", path: "/settings#credits" }, warning: true },
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
  if (moment.id === highlightId) item.className = "highlighted";
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
  if (moment.ai_text) {
    const line = add("ai", "");
    const text = document.createElement("span");
    text.textContent = moment.ai_text;
    line.append(sparkle(), text);
  }
  if (moment.note) add("note", moment.note);
  const status = moment.ai_text ? null : STATUS[moment.ai_status];
  if (status) {
    const line = document.createElement("p");
    line.className = `moment-status${status.warning ? " warning" : ""}`;
    line.textContent = status.text;
    if (status.warning) line.prepend(coin());
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
// The moment just saved, highlighted and scrolled to like on the web app.
let highlightId = null;
let scrollToHighlight = false;

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
    // Keep what's shown and try again while polling; say so only if nothing loaded yet.
    if (!list.querySelector("li:not(.muted)")) {
      const failed = document.createElement("li");
      failed.className = "muted";
      failed.textContent = "Couldn't load this video's moments.";
      list.replaceChildren(failed);
    }
    if (Date.now() < pollUntil) pollTimer = setTimeout(() => void renderMoments(tab, videoId), POLL_MS);
    return;
  }
  list.replaceChildren(...moments.map((moment) => momentRow(tab, moment)));
  $("moment-count").textContent = moments.length === 1 ? "1 moment" : `${moments.length} moments`;
  if (scrollToHighlight) {
    scrollToHighlight = false;
    list.querySelector(".highlighted")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
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

/** One line like the web app's note field, growing to five lines as the note gets longer. */
function fitNote() {
  const note = $("note");
  note.style.height = "auto";
  note.style.height = `${Math.min(note.scrollHeight + 2, 128)}px`;
  note.style.overflowY = note.scrollHeight + 2 > 128 ? "auto" : "hidden";
}

async function shortcutLabel() {
  const commands = await chrome.commands.getAll();
  return commands.find((command) => command.name === "capture-moment")?.shortcut || "Alt+S";
}

/** The save options menu beside Save moment, as in the web app. */
/**
 * Shows the credit balance where it matters: in the menu's AI line cost, and
 * as a notice above Save moment when the default would need a credit and none
 * are left. Saving still works; the moment is kept without an AI line.
 */
function showCredits(balance, aiDefault) {
  const option = $("capture-menu").querySelector('.option[data-ai="true"]');
  const cost = option.querySelector(".cost");
  const empty = balance <= 0;
  cost.textContent = empty ? "No credits" : `1 credit · ${balance} left`;
  option.classList.toggle("empty", empty);
  $("credits-notice").classList.toggle("hidden", !(empty && aiDefault));
}

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
  onClick("brand", () => openTab("/"));
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
    // YouTube moved on to another video while the popup was open: show that one instead.
    if (latest.videoId !== video.videoId) {
      location.reload();
      return;
    }
    try {
      if (latest.ad) {
        feedback(MESSAGES.ad, "error");
        return;
      }
      const result = await capture({ ...latest, note: $("note").value.trim(), ai });
      $("note").value = "";
      fitNote();
      const at = formatClock(latest.seconds);
      // The web app's wording.
      feedback(result.merged ? `Added to your moment near ${at}` : `Moment saved at ${at}`, "success");
      highlightId = result.moment?.id ?? null;
      scrollToHighlight = true;
      refreshMoments(tab, video.videoId);
      void refreshCredits();
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
    if (!current) return;
    // Autoplay or navigation changed the video; reopen the popup's view for it.
    if (current.videoId !== video.videoId) location.reload();
    else showPlayhead(current);
  }, 500);
  onClick("open-video", () => openTab(`/v/${video.videoId}`));

  let aiDefault = null;
  // A save with an AI line spends a credit, so the balance is re-read after each save.
  async function refreshCredits() {
    if (aiDefault === null) return;
    try {
      showCredits((await api("/users/me")).credits_balance, aiDefault);
    } catch {
      // Keep the last balance shown.
    }
  }
  onClick("get-credits", () => openTab("/settings#credits"));
  $("credits-notice").querySelector(".coin").replaceWith(coin());

  try {
    const profile = await api("/users/me");
    aiDefault = Boolean(profile.ai_moments_default);
    setupMenu(aiDefault, save);
    showCredits(profile.credits_balance, aiDefault);
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
  $("note").addEventListener("input", fitNote);
  $("note").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("capture-form").requestSubmit();
    }
  });
}

void init();
