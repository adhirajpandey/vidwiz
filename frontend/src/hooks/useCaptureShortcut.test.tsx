// @vitest-environment jsdom
import { act, cleanup, fireEvent, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useCaptureShortcut } from './useCaptureShortcut';
import type { CaptureOutcome } from './useCaptureShortcut';

function event<T>() {
  const listeners = new Set<(value: T) => void>();
  return {
    addListener: (listener: (value: T) => void) => listeners.add(listener),
    emit: (value: T) => { listeners.forEach(listener => listener(value)); },
  };
}
function extension(shortcut = 'Alt+S', protocol = 1) {
  const ports: ReturnType<typeof makePort>[] = [];
  function makePort() {
    return {
      onMessage: event<Record<string, unknown>>(), onDisconnect: event<void>(),
      postMessage: vi.fn(), disconnect: vi.fn(),
    };
  }
  const runtime = {
    lastError: undefined as { message: string } | undefined,
    sendMessage: vi.fn((_id: string, _message: unknown, reply: (value: unknown) => void) => reply({ protocol, shortcut })),
    connect: vi.fn(() => { const port = makePort(); ports.push(port); return port; }),
  };
  vi.stubGlobal('chrome', { runtime });
  return { runtime, ports, ready: () => ports.at(-1)!.onMessage.emit({ type: 'READY', protocol: 1, shortcut }) };
}
const capture = () => vi.fn(async (): Promise<CaptureOutcome> => 'saved');
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); document.body.replaceChildren(); });

it('uses standalone Alt+S and ignores repeat, modifiers, composition, typing, menus, and hidden tabs', async () => {
  vi.stubGlobal('chrome', undefined);
  const save = capture();
  const { result } = renderHook(() => useCaptureShortcut(save));
  expect(result.current).toEqual({ state: 'standalone', shortcut: 'Alt+S' });
  for (const extra of [{ repeat: true }, { shiftKey: true }, { ctrlKey: true }, { metaKey: true }, { isComposing: true }]) {
    fireEvent.keyDown(document.body, { key: 's', altKey: true, ...extra });
  }
  const input = document.createElement('input'); document.body.append(input); input.focus();
  fireEvent.keyDown(input, { key: 's', altKey: true }); input.blur();
  const menu = document.createElement('div'); menu.setAttribute('role', 'menu'); document.body.append(menu);
  fireEvent.keyDown(document.body, { key: 's', altKey: true }); menu.remove();
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValueOnce('hidden');
  fireEvent.keyDown(document.body, { key: 's', altKey: true });
  expect(save).not.toHaveBeenCalled();
  await act(async () => fireEvent.keyDown(document.body, { key: 'ß', code: 'KeyS', altKey: true }));
  expect(save).toHaveBeenCalledTimes(1);
});

it('receives the assigned extension shortcut, uses the same save, and acknowledges each id only once', async () => {
  const ext = extension('Ctrl+Shift+Y');
  const save = capture();
  const { result } = renderHook(() => useCaptureShortcut(save));
  act(ext.ready);
  expect(result.current).toEqual({ state: 'connected', shortcut: 'Ctrl+Shift+Y' });
  fireEvent.keyDown(document.body, { key: 's', altKey: true });
  expect(save).not.toHaveBeenCalled();
  const port = ext.ports[0];
  await act(async () => {
    port.onMessage.emit({ type: 'CAPTURE', id: 'one' });
    port.onMessage.emit({ type: 'CAPTURE', id: 'one' });
  });
  expect(save).toHaveBeenCalledTimes(1);
  expect(port.postMessage).toHaveBeenCalledExactlyOnceWith({ type: 'CAPTURE_RESULT', id: 'one', outcome: 'saved' });
});

it('ignores forwarded commands while typing or a dialog is open, but allows player iframe focus', async () => {
  const ext = extension(); const save = capture();
  renderHook(() => useCaptureShortcut(save)); act(ext.ready);
  const input = document.createElement('textarea'); document.body.append(input); input.focus();
  await act(async () => ext.ports[0].onMessage.emit({ type: 'CAPTURE', id: 'typing' }));
  expect(save).not.toHaveBeenCalled(); input.remove();
  const dialog = document.createElement('div'); dialog.setAttribute('role', 'dialog'); document.body.append(dialog);
  await act(async () => ext.ports[0].onMessage.emit({ type: 'CAPTURE', id: 'dialog' }));
  expect(save).not.toHaveBeenCalled(); dialog.remove();
  const iframe = document.createElement('iframe'); document.body.append(iframe); iframe.focus();
  await act(async () => ext.ports[0].onMessage.emit({ type: 'CAPTURE', id: 'player' }));
  expect(save).toHaveBeenCalledTimes(1);
});

it('reconnects after worker disconnect and never replays an earlier capture', async () => {
  vi.useFakeTimers();
  const ext = extension(); const save = capture();
  const { result, unmount } = renderHook(() => useCaptureShortcut(save)); act(ext.ready);
  await act(async () => ext.ports[0].onMessage.emit({ type: 'CAPTURE', id: 'old' }));
  act(() => ext.ports[0].onDisconnect.emit());
  expect(result.current.state).toBe('disconnected');
  act(() => vi.advanceTimersByTime(250)); act(ext.ready);
  expect(ext.ports).toHaveLength(2);
  expect(save).toHaveBeenCalledTimes(1);
  // Stale messages cannot capture on the new page connection.
  await act(async () => ext.ports[0].onMessage.emit({ type: 'CAPTURE', id: 'stale' }));
  expect(save).toHaveBeenCalledTimes(1);
  unmount();
  expect(ext.ports[1].disconnect).toHaveBeenCalled();
  act(() => vi.runAllTimers());
  expect(ext.ports).toHaveLength(2);
});

it('handles old and missing extensions and preserves an unassigned shortcut', () => {
  const old = extension('Alt+S', 0);
  const outdated = renderHook(() => useCaptureShortcut(capture()));
  expect(outdated.result.current).toEqual({ state: 'outdated', shortcut: null });
  expect(old.runtime.connect).not.toHaveBeenCalled(); outdated.unmount();
  const missing = extension();
  missing.runtime.sendMessage.mockImplementation((_id, _message, reply) => {
    missing.runtime.lastError = { message: 'Receiving end does not exist' }; reply(undefined); missing.runtime.lastError = undefined;
  });
  const standalone = renderHook(() => useCaptureShortcut(capture()));
  expect(standalone.result.current).toEqual({ state: 'standalone', shortcut: 'Alt+S' }); standalone.unmount();
  const unassigned = extension('');
  const connected = renderHook(() => useCaptureShortcut(capture())); act(unassigned.ready);
  expect(connected.result.current).toEqual({ state: 'connected', shortcut: null });
});

it('refreshes shortcut assignment on focus and bounds retries when the worker stays unavailable', () => {
  vi.useFakeTimers();
  const ext = extension();
  const { result } = renderHook(() => useCaptureShortcut(capture())); act(ext.ready);
  ext.runtime.sendMessage.mockImplementation((_id, _message, reply) => reply({ protocol: 1, shortcut: '' }));
  fireEvent.focus(window);
  act(() => ext.ports.at(-1)!.onMessage.emit({ type: 'READY', protocol: 1, shortcut: '' }));
  expect(result.current.shortcut).toBeNull();
  ext.runtime.sendMessage.mockImplementation((_id, _message, reply) => {
    ext.runtime.lastError = { message: 'Unavailable' }; reply(undefined); ext.runtime.lastError = undefined;
  });
  act(() => ext.ports.at(-1)!.onDisconnect.emit());
  act(() => vi.runAllTimers());
  expect(result.current.state).toBe('disconnected');
  expect(ext.runtime.sendMessage.mock.calls.length).toBeLessThanOrEqual(8);
  expect(vi.getTimerCount()).toBe(0);
});
