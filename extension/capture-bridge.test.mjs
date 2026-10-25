import assert from "node:assert/strict";
import { it } from "node:test";
import { createCaptureBridge } from "./capture-bridge.js";

function event() {
  const listeners = new Set();
  return { addListener: (listener) => listeners.add(listener), emit: (...args) => [...listeners].map((listener) => listener(...args)) };
}
function setup(t) {
  let key = "Alt+S";
  const ports = [];
  const badges = [];
  const browser = {
    runtime: { onMessageExternal: event(), onConnectExternal: event() },
    commands: { getAll: async () => [{ name: "capture-moment", shortcut: key }] },
    action: { setBadgeText: (value) => badges.push(value), setTitle: () => {} },
  };
  const bridge = createCaptureBridge(browser, "https://vidwiz.online");
  const sender = (id) => ({ origin: "https://vidwiz.online", frameId: 0, tab: { id } });
  const connect = async (id, overrides = {}) => {
    const port = {
      name: "vidwiz-capture-v1", sender: { ...sender(id), ...overrides }, messages: [], disconnected: false,
      onMessage: event(), onDisconnect: event(),
      postMessage(message) { if (this.disconnected) throw new Error("Disconnected port"); this.messages.push(message); },
      disconnect() { this.disconnected = true; },
      remoteDisconnect() { this.disconnected = true; this.onDisconnect.emit(); },
    };
    ports.push(port);
    browser.runtime.onConnectExternal.emit(port);
    await Promise.resolve();
    return port;
  };
  t.after(() => ports.forEach((port) => port.remoteDisconnect()));
  return { bridge, browser, sender, connect, badges, setKey: (value) => { key = value; } };
}
const tab = (id, url = "https://vidwiz.online/v/aaaaaaaaaaa") => ({ id, url });
const captures = (port) => port.messages.filter((message) => message.type === "CAPTURE");

it("reports the assigned or unassigned shortcut only to trusted top-level web tabs", async (t) => {
  const { browser, sender, setKey } = setup(t);
  let reply;
  const ask = (who) => browser.runtime.onMessageExternal.emit({ type: "CAPTURE_CAPABILITIES" }, who, (value) => { reply = value; });
  assert.deepEqual(ask(sender(1)), [true]);
  await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(reply, { protocol: 1, shortcut: "Alt+S" });
  setKey(""); ask(sender(1)); await Promise.resolve(); await Promise.resolve();
  assert.equal(reply.shortcut, "");
  for (const invalid of [{ ...sender(1), origin: "https://other.example" }, { ...sender(1), frameId: 1 }, { origin: "https://vidwiz.online" }]) {
    assert.deepEqual(ask(invalid), [false]);
  }
});

it("rejects connections from another origin or a child frame", async (t) => {
  const { connect } = setup(t);
  assert.equal((await connect(1, { origin: "https://other.example" })).disconnected, true);
  assert.equal((await connect(1, { frameId: 2 })).disconnected, true);
});

it("forwards only to the requested video tab and leaves YouTube and unrelated tabs to their handlers", async (t) => {
  const { bridge, connect, badges } = setup(t);
  const first = await connect(1), second = await connect(2);
  assert.equal(await bridge.capture(tab(3, "https://www.youtube.com/watch?v=aaaaaaaaaaa")), false);
  assert.equal(await bridge.capture(tab(3, "https://other.example/v/aaaaaaaaaaa")), false);
  assert.equal(await bridge.capture(tab(3, "https://vidwiz.online/library")), true);
  assert.equal(badges.some((badge) => badge.text === "!"), false);
  await bridge.capture(tab(2));
  assert.equal(captures(first).length, 0);
  assert.equal(captures(second).length, 1);
});

it("holds one command until acknowledged and refreshes remapped shortcut labels", async (t) => {
  const { bridge, connect, setKey } = setup(t);
  const port = await connect(1);
  setKey("Ctrl+Shift+Y");
  await Promise.all([bridge.capture(tab(1)), bridge.capture(tab(1))]);
  assert.equal(captures(port).length, 1);
  assert.equal(port.messages.at(-2).shortcut, "Ctrl+Shift+Y");
  port.onMessage.emit({ type: "CAPTURE_RESULT", id: "wrong" });
  await bridge.capture(tab(1));
  assert.equal(captures(port).length, 1);
  port.onMessage.emit({ type: "CAPTURE_RESULT", id: captures(port)[0].id, outcome: "saved" });
  await bridge.capture(tab(1));
  assert.equal(captures(port).length, 2);
});

it("replaces connections without an old disconnect deleting the new tab connection", async (t) => {
  const { bridge, connect } = setup(t);
  const old = await connect(1), current = await connect(1);
  old.onDisconnect.emit();
  await bridge.capture(tab(1));
  assert.equal(captures(old).length, 0);
  assert.equal(captures(current).length, 1);
});

it("does not replay captures after timeout or reconnect", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { bridge, connect, badges } = setup(t);
  const old = await connect(1);
  await bridge.capture(tab(1));
  t.mock.timers.tick(30_000);
  assert.equal(captures(old).length, 1);
  old.remoteDisconnect();
  await bridge.capture(tab(1));
  assert.ok(badges.some((badge) => badge.text === "!"));
  const current = await connect(1);
  assert.equal(captures(current).length, 0);
  await bridge.capture(tab(1));
  assert.equal(captures(current).length, 1);
});

it("removes a failed handshake without relying on a local disconnect event", async (t) => {
  const { bridge, browser, connect, badges } = setup(t);
  browser.commands.getAll = async () => { throw new Error("Shortcut unavailable"); };
  const port = await connect(1);
  await Promise.resolve(); await Promise.resolve();
  assert.equal(port.disconnected, true);
  await bridge.capture(tab(1));
  assert.ok(badges.some((badge) => badge.text === "!"));
});

it("removes a connection after command failure and allows a fresh connection", async (t) => {
  const { bridge, browser, connect, badges } = setup(t);
  const old = await connect(1);
  const getAll = browser.commands.getAll;
  browser.commands.getAll = async () => { throw new Error("Shortcut unavailable"); };
  await bridge.capture(tab(1));
  assert.equal(old.disconnected, true);
  await bridge.capture(tab(1));
  assert.ok(badges.some((badge) => badge.text === "!"));
  browser.commands.getAll = getAll;
  const current = await connect(1);
  await bridge.capture(tab(1));
  assert.equal(captures(old).length, 0);
  assert.equal(captures(current).length, 1);
});

it("wires web commands without the login listener swallowing the capability response", async (t) => {
  const previous = globalThis.chrome;
  const messages = [];
  const browser = {
    runtime: { onMessageExternal: event(), onConnectExternal: event(), onInstalled: event() },
    commands: { getAll: async () => [{ name: "capture-moment", shortcut: "Alt+S" }], onCommand: event() },
    tabs: { query: async () => [tab(1)], onUpdated: event(), sendMessage: () => { throw new Error("Must not read the YouTube content script on a web tab"); } },
    action: { setBadgeText: () => {}, setTitle: () => {} },
  };
  globalThis.chrome = browser;
  t.after(() => { if (previous === undefined) delete globalThis.chrome; else globalThis.chrome = previous; });
  await import(`./background.js?capture-test=${Date.now()}`);
  const sender = { origin: "https://vidwiz.online", frameId: 0, tab: { id: 1 } };
  const replies = [];
  browser.runtime.onMessageExternal.emit({ type: "CAPTURE_CAPABILITIES" }, sender, (reply) => replies.push(reply));
  await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(replies, [{ protocol: 1, shortcut: "Alt+S" }]);
  const port = { name: "vidwiz-capture-v1", sender, onMessage: event(), onDisconnect: event(), postMessage: (message) => messages.push(message), disconnect() {} };
  t.after(() => port.onDisconnect.emit());
  browser.runtime.onConnectExternal.emit(port);
  await Promise.all(browser.commands.onCommand.emit("capture-moment"));
  assert.equal(messages.filter((message) => message.type === "CAPTURE").length, 1);
});
