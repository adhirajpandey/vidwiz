import { ApiError, MESSAGES, api, capture, formatClock, getToken, isVideoUrl, playFrom, webUrl } from "./api.js";
import { tooltip } from "./tooltip.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["login-view", "idle-view", "reload-view", "capture-view"];
const show = (id) => {
  for (const view of VIEWS) $(view).classList.toggle("hidden", view !== id);
  // The video card opens VidWiz; other views keep the header link.
  $("profile").classList.add("hidden");
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

function showProfile(profile) {
  if ($("capture-view").classList.contains("hidden")) return;
  const name = profile.name || profile.email || "Account";
  const credits = profile.credits_balance === 1 ? "1 credit" : `${profile.credits_balance} credits`;
  $("profile").setAttribute("aria-label", `${name}, ${credits}. Open Settings`);
  tooltip($("profile"), [name, credits, "Open Settings"]);
  $("profile-initial").textContent = name.slice(0, 1).toUpperCase();
  const image = $("profile-image");
  image.onerror = () => image.classList.add("hidden");
  if (profile.profile_image_url && image.getAttribute("src") !== profile.profile_image_url) {
    image.classList.remove("hidden");
    image.src = profile.profile_image_url;
  } else if (!profile.profile_image_url) {
    image.classList.add("hidden");
    image.removeAttribute("src");
  }
  $("open-app").classList.add("hidden");
  $("profile").classList.remove("hidden");
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
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "AI-generated line");
  tooltip(svg, "AI-generated line");
  svg.innerHTML = '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>';
  return svg;
}

function momentRow(tab, moment) {
  const start = playFrom(moment);
  const item = document.createElement("li");
  item.classList.toggle("highlighted", moment.id === highlightId);
  item.classList.toggle("editing", moment.id === editingId);
  item.classList.toggle("confirming", moment.id === confirmingId);
  const time = document.createElement("button");
  time.className = "time tabular";
  time.textContent = formatClock(moment.at_seconds);
  time.setAttribute("aria-label", `Play from ${formatClock(start)}`);
  tooltip(time, `Play from ${formatClock(start)}`);
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
  // While the note is being edited, the field takes its place.
  if (moment.note && editingId !== moment.id) add("note", moment.note);
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
  if (editingId === moment.id) body.append(noteEditor(tab, moment));
  if (confirmingId === moment.id) body.append(deleteConfirm(tab, moment));
  item.append(time, body, momentActions(tab, moment));
  return item;
}

// A click outside a moment's "…" menu closes it.
document.addEventListener("click", (event) => {
  if (!event.target.closest?.(".actions")) closeActionsMenu?.();
});

// One row at a time can edit its note or confirm a delete. While it does, the
// list doesn't redraw, so a refresh can't wipe what the user is typing.
let editingId = null;
let confirmingId = null;
let closeActionsMenu = null;
// True while a row's edit or delete request is out. The row stays as it is
// until the request ends, so nothing can start a second one or drop the draft.
let mutating = false;
const busy = () => editingId !== null || confirmingId !== null;

function setRowState(tab, { editing = null, confirming = null }) {
  if (mutating) return;
  editingId = editing;
  confirmingId = confirming;
  paint(tab);
  const row = $("moments").querySelector(".editing textarea, .confirming .confirm-delete");
  row?.focus();
}

/** The "…" menu on a moment, like the web app's: add or edit the note, or delete. */
function momentActions(tab, moment) {
  const wrap = document.createElement("div");
  wrap.className = "actions";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "actions-toggle";
  toggle.setAttribute("aria-label", "Moment actions");
  tooltip(toggle, "Moment actions");
  toggle.setAttribute("aria-haspopup", "menu");
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><g fill="currentColor"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></g></svg>';
  const menu = document.createElement("div");
  menu.className = "actions-menu hidden";
  menu.setAttribute("role", "menu");
  const item = (label, className, onSelect) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `option ${className}`;
    button.setAttribute("role", "menuitem");
    button.textContent = label;
    button.addEventListener("click", () => { close(); onSelect(); });
    menu.append(button);
    return button;
  };
  item(moment.note ? "Edit note" : "Add note", "", () => setRowState(tab, { editing: moment.id }));
  item("Delete", "destructive", () => setRowState(tab, { confirming: moment.id }));

  function close() {
    menu.classList.add("hidden");
    toggle.setAttribute("aria-expanded", "false");
    if (closeActionsMenu === close) closeActionsMenu = null;
  }
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!menu.classList.contains("hidden")) return close();
    closeActionsMenu?.();
    menu.classList.remove("hidden");
    toggle.setAttribute("aria-expanded", "true");
    closeActionsMenu = close;
    menu.querySelector("button").focus();
  });
  menu.addEventListener("keydown", (event) => {
    const items = [...menu.querySelectorAll("button")];
    const index = items.indexOf(document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      toggle.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      items[(index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    }
  });
  wrap.append(toggle, menu);
  return wrap;
}

function rowError(container, error) {
  if (error instanceof ApiError && error.status === 401) {
    showLogin(error.message);
    return;
  }
  let line = container.querySelector(".row-error");
  if (!line) {
    line = document.createElement("p");
    line.className = "row-error";
    line.setAttribute("role", "alert");
    container.append(line);
  }
  line.textContent = error.message;
}

/** Edits the note in place: Enter saves, Shift+Enter adds a line, Esc cancels. Empty removes it. */
function noteEditor(tab, moment) {
  const form = document.createElement("form");
  form.className = "note-editor";
  const field = document.createElement("textarea");
  field.rows = 1;
  field.value = moment.note ?? "";
  field.placeholder = "Note";
  field.setAttribute("aria-label", "Note");
  const buttons = document.createElement("div");
  buttons.className = "row-buttons";
  const save = document.createElement("button");
  save.type = "submit";
  save.className = "primary small";
  save.textContent = "Save";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost small";
  cancel.textContent = "Cancel";
  buttons.append(save, cancel);
  form.append(field, buttons);

  const done = () => setRowState(tab, {});
  cancel.addEventListener("click", done);
  field.addEventListener("input", () => fit(field));
  field.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      done();
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    // Enter submits even with Save disabled, so check for a request already out.
    if (mutating) return;
    mutating = true;
    save.disabled = cancel.disabled = field.readOnly = true;
    try {
      const updated = await api(`/moments/${moment.id}`, { method: "PATCH", body: { note: field.value.trim() || null } });
      lastMoments = lastMoments.map((item) => (item.id === moment.id ? updated : item));
      mutating = false;
      done();
    } catch (error) {
      mutating = false;
      save.disabled = cancel.disabled = field.readOnly = false;
      rowError(form, error);
    }
  });
  requestAnimationFrame(() => {
    fit(field);
    field.setSelectionRange(field.value.length, field.value.length);
  });
  return form;
}

/** Asks before deleting, inside the row; there is no undo. */
function deleteConfirm(tab, moment) {
  const bar = document.createElement("div");
  bar.className = "delete-bar";
  const label = document.createElement("span");
  label.textContent = "Delete this moment?";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger small confirm-delete";
  remove.textContent = "Delete";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost small";
  cancel.textContent = "Cancel";
  bar.append(label, remove, cancel);
  const done = () => setRowState(tab, {});
  cancel.addEventListener("click", done);
  bar.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      done();
    }
  });
  remove.addEventListener("click", async () => {
    if (mutating) return;
    mutating = true;
    remove.disabled = cancel.disabled = true;
    try {
      await api(`/moments/${moment.id}`, { method: "DELETE" });
      lastMoments = lastMoments.filter((item) => item.id !== moment.id);
      if (highlightId === moment.id) highlightId = null;
      mutating = false;
      done();
    } catch (error) {
      mutating = false;
      remove.disabled = cancel.disabled = false;
      rowError(bar, error);
    }
  });
  return bar;
}

// While an AI line is on its way, refresh the list like the web app does.
const POLL_MS = 3000;
const POLL_LIMIT_MS = 3 * 60 * 1000;
let pollTimer = null;
let pollUntil = 0;
// The moment just saved, highlighted and scrolled to like on the web app.
let highlightId = null;
let scrollToHighlight = false;

let lastMoments = [];

async function renderMoments(tab, videoId) {
  clearTimeout(pollTimer);
  if (busy()) {
    // Check again after the edit or delete finishes.
    if (Date.now() < pollUntil) pollTimer = setTimeout(() => void renderMoments(tab, videoId), POLL_MS);
    return;
  }
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
  lastMoments = moments;
  paint(tab);
  if (moments.some(isPending) && Date.now() < pollUntil) {
    pollTimer = setTimeout(() => void renderMoments(tab, videoId), POLL_MS);
  }
}

/** Draws the list from the last loaded moments. */
function paint(tab) {
  closeActionsMenu = null;
  const list = $("moments");
  const moments = lastMoments;
  list.replaceChildren(...moments.map((moment) => momentRow(tab, moment)));
  list.classList.toggle("busy", busy());
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
}

function refreshMoments(tab, videoId) {
  pollUntil = Date.now() + POLL_LIMIT_MS;
  void renderMoments(tab, videoId);
}

/** One line like the web app's note field, growing to five lines as the note gets longer. */
function fit(field) {
  field.style.height = "auto";
  field.style.height = `${Math.min(field.scrollHeight + 2, 128)}px`;
  field.style.overflowY = field.scrollHeight + 2 > 128 ? "auto" : "hidden";
}
const fitNote = () => fit($("note"));

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
let creditBalance = null;
function showCredits(balance, aiDefault) {
  creditBalance = balance;
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
    // These save right away; the default only changes in Settings.
    tooltip(option, () => {
      if (option.dataset.ai === "false") return "Save this moment without an AI line";
      return creditBalance !== null && creditBalance <= 0 ? "Save this moment. No credits left, so it won't get an AI line" : "Save this moment with an AI line";
    });
    option.addEventListener("click", () => {
      close();
      void save(option.dataset.ai === "true");
    });
  }

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
  $("profile").href = webUrl("/settings");
  onClick("profile", () => openTab("/settings"));
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
  // The icon adds a note, then edits the open draft.
  function noteOpen(open) {
    $("capture-note").classList.toggle("hidden", !open);
    $("add-note").setAttribute("aria-expanded", String(open));
    $("add-note").setAttribute("aria-label", open ? "Edit note" : "Add note");
  }
  tooltip($("add-note"), () => $("add-note").getAttribute("aria-label"));
  function resetNote() {
    $("note").value = "";
    $("note").style.height = "";
    $("note").style.overflowY = "";
    noteOpen(false);
  }
  $("add-note").addEventListener("click", () => {
    noteOpen(true);
    fitNote();
    $("note").focus();
  });
  $("cancel-note").addEventListener("click", () => {
    resetNote();
    $("add-note").focus();
  });

  let saving = false;
  let ad = video.ad;
  const setDisabled = () => {
    for (const button of buttons()) button.disabled = saving || ad;
    // Lock the draft during a request so success cannot erase newer edits.
    for (const id of ["note", "add-note", "cancel-note"]) $(id).disabled = saving;
  };

  /** `ai` undefined lets the server apply the user's default. */
  async function save(ai) {
    if (saving || ad) return;
    saving = true;
    let focusSave = false;
    const startedInForm = $("capture-form").contains(document.activeElement);
    setDisabled();
    // Save where the video is now, not where it was when the popup opened.
    const latest = await currentVideo(tab);
    // The tab left this video while the popup was open: show what it has now
    // instead of saving to a video that is no longer there.
    if (latest?.videoId !== video.videoId) {
      location.reload();
      return;
    }
    try {
      if (latest.ad) {
        feedback(MESSAGES.ad, "error");
        return;
      }
      const result = await capture({ ...latest, note: $("note").value.trim(), ai });
      saves += 1;
      // Disabled controls lose focus; restore it unless the user moved elsewhere.
      focusSave = startedInForm && (document.activeElement === document.body || $("capture-form").contains(document.activeElement));
      resetNote();
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
      if (focusSave) $("capture").focus();
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

  // Wire saving before the controls show, so a save made before the profile
  // loads uses the server's default instead of submitting the page.
  let saves = 0;
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

  show("capture-view");
  // The full title and channel when the card cuts them short.
  tooltip($("video-card"), () => {
    const title = $("video-title"), channel = $("video-channel");
    return [
      title.scrollHeight > title.clientHeight + 1 && video.title,
      channel.scrollWidth > channel.clientWidth && video.channel,
      "Open video in VidWiz",
    ];
  });
  $("video-title").textContent = video.title;
  $("video-channel").textContent = video.channel || "";
  $("video-channel").classList.toggle("hidden", !video.channel);
  const thumbnail = $("video-thumbnail");
  thumbnail.onerror = () => thumbnail.classList.add("hidden");
  thumbnail.src = `https://i.ytimg.com/vi/${video.videoId}/mqdefault.jpg`;
  $("video-card").href = webUrl(`/v/${video.videoId}`);
  $("capture-time").textContent = `at ${formatClock(video.seconds)}`;
  if (ad) feedback(MESSAGES.ad);
  setDisabled();
  setInterval(async () => {
    const current = await currentVideo(tab);
    // Autoplay or navigation changed the video, or the tab left it; reopen the
    // popup's view for what the tab shows now.
    if (current?.videoId !== video.videoId) location.reload();
    else showPlayhead(current);
  }, 500);
  onClick("video-card", () => openTab(`/v/${video.videoId}`));

  let aiDefault = null;
  // What Save moment will do now; unknown until the profile loads.
  tooltip($("capture"), () => {
    if (saving) return "Saving this moment…";
    if (ad) return "Saving is paused while an ad plays";
    if (aiDefault === null) return "Saves with your AI line default";
    if (!aiDefault) return "Saves without an AI line, your default. Free";
    if (creditBalance !== null && creditBalance <= 0) return "Saves without an AI line: no credits left";
    return "Saves with an AI line, your default. 1 credit";
  });
  // A save with an AI line spends a credit, so the balance is re-read after each save.
  async function refreshCredits() {
    if (aiDefault === null) return;
    try {
      const profile = await api("/users/me");
      showCredits(profile.credits_balance, aiDefault);
      showProfile(profile);
    } catch {
      // Keep the last balance shown.
    }
  }
  onClick("get-credits", () => openTab("/settings#credits"));
  $("credits-notice").querySelector(".coin").replaceWith(coin());

  try {
    const savesBefore = saves;
    const profile = await api("/users/me");
    showProfile(profile);
    aiDefault = Boolean(profile.ai_moments_default);
    setupMenu(aiDefault, save);
    showCredits(profile.credits_balance, aiDefault);
    setDisabled();
    // A save during the request may have spent a credit after it was read.
    if (saves !== savesBefore) void refreshCredits();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showLogin(error.message);
      return;
    }
    // Without the profile, Save moment still works with the server's default.
  }
  refreshMoments(tab, video.videoId);
}

void init();
