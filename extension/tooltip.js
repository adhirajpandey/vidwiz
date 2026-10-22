// One shared tooltip for the popup's icons and actions. It shows on hover and
// on keyboard focus, sits outside scrolling lists so nothing clips it, and
// closes on Escape, a click, or when its control goes away.
//
// Give a control `data-tooltip="Text"`, or call `tooltip(element, text)` where
// text can be a function returning lines, read each time it shows.

const HOVER_DELAY_MS = 400;
const GAP = 6;
const EDGE = 6;

const providers = new WeakMap();
const box = document.createElement("div");
box.className = "tooltip hidden";
box.setAttribute("role", "tooltip");
box.id = "tooltip";

let anchor = null;
let showTimer = null;
let hideTimer = null;
// The control just clicked or dismissed stays quiet until the pointer leaves it.
let quiet = null;

/** Sets a control's tooltip: a string, or a function returning a string or lines. */
export function tooltip(element, text) {
  providers.set(element, text);
  element.dataset.tooltip = "";
  if (anchor === element) render();
}

const target = (node) => node?.closest?.("[data-tooltip]") ?? null;

function lines(element) {
  const provider = providers.get(element) ?? element.dataset.tooltip;
  const value = typeof provider === "function" ? provider() : provider;
  return (Array.isArray(value) ? value : [value]).filter(Boolean);
}

// A menu's tooltips sit beside the whole menu so they don't cover its other items.
const frame = (element) => element.closest('[role="menu"]') ?? element;

// Hidden, removed, or scrolled out of its list: nothing to point at.
function visible(element) {
  if (!element.isConnected || !element.getClientRects().length) return false;
  // A menu that opens from it is showing instead.
  if (element.matches('[aria-haspopup][aria-expanded="true"]')) return false;
  const list = element.closest(".moments");
  if (!list) return true;
  const rect = element.getBoundingClientRect();
  const view = list.getBoundingClientRect();
  return rect.bottom > view.top && rect.top < view.bottom;
}

function render() {
  const text = anchor && visible(anchor) ? lines(anchor) : [];
  if (!text.length) return hide();
  box.replaceChildren(...text.map((line) => Object.assign(document.createElement("span"), { textContent: line })));
  box.classList.remove("hidden");
  place();
}

// Below the control, or above it near the popup's bottom, kept inside the popup.
function place() {
  const rect = frame(anchor).getBoundingClientRect();
  const { width, height } = box.getBoundingClientRect();
  let top = rect.bottom + GAP;
  if (top + height > innerHeight - EDGE) top = rect.top - GAP - height;
  top = Math.max(EDGE, Math.min(top, innerHeight - EDGE - height));
  const left = Math.max(EDGE, Math.min(rect.left + rect.width / 2 - width / 2, innerWidth - EDGE - width));
  box.style.top = `${Math.round(top)}px`;
  box.style.left = `${Math.round(left)}px`;
}

function show(element) {
  clearTimeout(showTimer);
  clearTimeout(hideTimer);
  if (anchor && anchor !== element) anchor.removeAttribute("aria-describedby");
  anchor = element;
  // Labelled icons already say it; elsewhere the tooltip describes the control.
  if (!anchor.hasAttribute("aria-label")) anchor.setAttribute("aria-describedby", box.id);
  render();
}

function hide() {
  clearTimeout(showTimer);
  clearTimeout(hideTimer);
  anchor?.removeAttribute("aria-describedby");
  anchor = null;
  box.classList.add("hidden");
}

document.body.append(box);

// Pointer events also reach disabled buttons, so a disabled Save can say why.
document.addEventListener("pointerover", (event) => {
  if (box.contains(event.target)) return clearTimeout(hideTimer);
  const element = target(event.target);
  if (!element || element === anchor || element === quiet) return;
  clearTimeout(showTimer);
  if (!box.classList.contains("hidden")) return show(element);
  showTimer = setTimeout(() => show(element), HOVER_DELAY_MS);
});
// Leaving waits a moment so the pointer can move onto the tooltip itself.
document.addEventListener("pointerout", (event) => {
  const from = box.contains(event.target) ? box : target(event.target);
  if (!from) return;
  const to = event.relatedTarget;
  if (to && (from.contains(to) || box.contains(to) || (anchor && anchor.contains(to)))) return;
  if (from === quiet) quiet = null;
  clearTimeout(showTimer);
  if (anchor && anchor === document.activeElement && anchor.matches(":focus-visible")) return;
  hideTimer = setTimeout(hide, 100);
});
document.addEventListener("focusin", (event) => {
  const element = target(event.target);
  if (element && element.matches(":focus-visible")) {
    quiet = null;
    show(element);
  }
  else if (anchor && !anchor.matches(":hover")) hide();
});
document.addEventListener("focusout", (event) => {
  if (event.target === anchor && !anchor.matches(":hover")) hide();
});
document.addEventListener("pointerdown", (event) => {
  quiet = target(event.target);
  hide();
}, true);
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !anchor) return;
  quiet = anchor;
  hide();
}, true);
document.addEventListener("scroll", () => anchor && render(), true);
// Rerendered rows, closed menus, and changed labels update or close it.
new MutationObserver((records) => {
  if (anchor && records.some((record) => !box.contains(record.target))) render();
}).observe(document.body, {
  subtree: true, childList: true, characterData: true, attributes: true,
  attributeFilter: ["class", "disabled", "aria-expanded", "aria-label", "hidden"],
});
