// Capture commands for web video pages. The page opens the connection; the
// extension chooses the active tab and never saves on the page's behalf.
const CHANNEL = "vidwiz-capture-v1";

export function createCaptureBridge(browser, webOrigin) {
  const connections = new Map();
  let sequence = 0;
  const shortcut = async () => (await browser.commands.getAll())
    .find((command) => command.name === "capture-moment")?.shortcut ?? "";
  const trusted = (sender) => sender?.origin === webOrigin
    && sender.frameId === 0 && Number.isInteger(sender.tab?.id);

  browser.runtime.onMessageExternal.addListener((message, sender, respond) => {
    if (message?.type !== "CAPTURE_CAPABILITIES" || !trusted(sender)) return false;
    shortcut().then((key) => respond({ protocol: 1, shortcut: key }), () => respond({ error: "Shortcut unavailable" }));
    return true;
  });

  browser.runtime.onConnectExternal.addListener((port) => {
    if (port.name !== CHANNEL || !trusted(port.sender)) { port.disconnect(); return; }
    const tabId = port.sender.tab.id;
    const previous = connections.get(tabId);
    if (previous) previous.port.disconnect();
    const connection = { port, pending: null, timer: null };
    connections.set(tabId, connection);
    port.onDisconnect.addListener(() => {
      clearTimeout(connection.timer);
      if (connections.get(tabId) === connection) connections.delete(tabId);
    });
    port.onMessage.addListener((message) => {
      if (message?.type !== "CAPTURE_RESULT" || message.id !== connection.pending) return;
      clearTimeout(connection.timer);
      connection.pending = null;
    });
    shortcut().then((key) => {
      if (connections.get(tabId) === connection) {
        browser.action.setBadgeText({ tabId, text: "" });
        browser.action.setTitle({ tabId, title: "VidWiz" });
        port.postMessage({ type: "READY", protocol: 1, shortcut: key });
      }
    }).catch(() => port.disconnect());
  });

  return {
    async capture(tab) {
      let url;
      try { url = new URL(tab.url); } catch { return false; }
      if (url.origin !== webOrigin) return false;
      if (!/^\/v\/[a-zA-Z0-9_-]{11}\/?$/.test(url.pathname)) return true;
      const connection = connections.get(tab.id);
      if (!connection) {
        browser.action.setBadgeText({ tabId: tab.id, text: "!" });
        browser.action.setTitle({ tabId: tab.id, title: "Open or reload a VidWiz video page to use the capture shortcut" });
        return true;
      }
      if (connection.pending !== null) return true;
      const id = `${Date.now()}-${++sequence}`;
      // Reserve before awaiting getAll, so overlapping commands share one save.
      connection.pending = id;
      try {
        const key = await shortcut();
        if (connections.get(tab.id) !== connection) return true;
        connection.port.postMessage({ type: "READY", protocol: 1, shortcut: key });
        connection.port.postMessage({ type: "CAPTURE", id });
        // A timeout releases the command lock, but never retries a capture.
        connection.timer = setTimeout(() => { connection.pending = null; }, 30_000);
      } catch {
        connection.pending = null;
        connection.port.disconnect();
      }
      return true;
    },
  };
}
