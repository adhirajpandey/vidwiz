import { ApiError, api, capture, formatClock, getToken, webUrl } from "./api.js";

const $ = (id) => document.getElementById(id);
const show = (id) => {
  for (const view of ["login-view", "idle-view", "capture-view"]) $(view).classList.toggle("hidden", view !== id);
};
const openTab = (path) => chrome.tabs.create({ url: webUrl(path) });

function feedback(text, kind = "") {
  const element = $("feedback");
  element.textContent = text;
  element.className = `feedback ${kind}`;
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function currentVideo(tab) {
  if (!tab?.id || !tab.url?.includes("youtube.com")) return null;
  try {
    return await chrome.tabs.sendMessage(tab.id, { action: "getVideo" });
  } catch {
    return null; // The page loaded before the extension; a reload fixes it.
  }
}

function momentText(moment) {
  if (moment.note) return { text: moment.note, pending: false };
  if (moment.ai_text) return { text: moment.ai_text, pending: false };
  if (moment.ai_status === "queued" || moment.ai_status === "waiting_transcript") return { text: "Writing the AI line…", pending: true };
  if (moment.quote) return { text: moment.quote, pending: false };
  return { text: "Saved moment", pending: true };
}

async function renderMoments(tab, videoId) {
  const list = $("moments");
  let moments;
  try {
    moments = await api(`/videos/${videoId}/moments`);
  } catch {
    list.replaceChildren();
    return;
  }
  list.replaceChildren(...moments.map((moment) => {
    const start = moment.quote_start_seconds ?? moment.at_seconds;
    const item = document.createElement("li");
    const time = document.createElement("button");
    time.className = "time";
    time.textContent = formatClock(start);
    time.setAttribute("aria-label", `Play from ${formatClock(start)}`);
    time.addEventListener("click", () => chrome.tabs.sendMessage(tab.id, { action: "seek", seconds: start }).catch(() => {}));
    const { text, pending } = momentText(moment);
    const label = document.createElement("span");
    label.className = `moment-text${pending ? " pending" : ""}`;
    label.textContent = text;
    item.append(time, label);
    return item;
  }));
  if (!moments.length) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "No moments yet.";
    list.append(empty);
  }
}

async function shortcutLabel() {
  const commands = await chrome.commands.getAll();
  return commands.find((command) => command.name === "capture-moment")?.shortcut || "Alt+S";
}

async function init() {
  $("open-app").addEventListener("click", (event) => { event.preventDefault(); openTab("/"); });
  $("login").addEventListener("click", () => openTab("/login"));
  $("shortcut").textContent = await shortcutLabel();

  if (!(await getToken())) {
    show("login-view");
    return;
  }
  const tab = await activeTab();
  const video = await currentVideo(tab);
  if (!video) {
    show("idle-view");
    return;
  }

  /** `ai` undefined lets the server apply the user's default. */
  async function save(ai) {
    const buttons = [$("capture"), $("capture-other")];
    if (buttons[0].disabled) return;
    for (const button of buttons) button.disabled = true;
    // Capture where the video is now, not where it was when the popup opened.
    const latest = (await currentVideo(tab)) || video;
    try {
      const result = await capture({ ...latest, note: $("note").value.trim(), ai });
      $("note").value = "";
      feedback(result.merged ? "Added to a nearby moment." : `Saved at ${formatClock(latest.seconds)}.`, "success");
      void renderMoments(tab, video.videoId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        $("login-reason").textContent = error.message;
        show("login-view");
      } else {
        feedback(error.message, "error");
      }
    } finally {
      for (const button of buttons) button.disabled = false;
    }
  }

  show("capture-view");
  $("video-title").textContent = video.title;
  $("capture-time").textContent = `at ${formatClock(video.seconds)}`;
  $("open-video").addEventListener("click", (event) => { event.preventDefault(); openTab(`/v/${video.videoId}`); });

  try {
    // Capture follows the user's AI line default; this button saves one moment the other way.
    const profile = await api("/users/me");
    const aiDefault = Boolean(profile.ai_moments_default);
    const other = $("capture-other");
    other.textContent = aiDefault ? "Save without AI line" : "Save with AI line, 1 credit";
    other.addEventListener("click", () => save(!aiDefault));
    other.classList.remove("hidden");
    $("capture").title = aiDefault ? "Saves with an AI line, 1 credit" : "Saves without an AI line";
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      $("login-reason").textContent = error.message;
      show("login-view");
      return;
    }
  }
  void renderMoments(tab, video.videoId);
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
