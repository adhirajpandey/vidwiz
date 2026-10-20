// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TranscriptPanel from './TranscriptPanel';

const segments = Array.from({ length: 30 }, (_, index) => ({
  start_seconds: index * 10, end_seconds: index * 10 + 10, text: `Line ${index}`,
}));
vi.mock('./queries', () => ({ useTranscript: () => ({ data: { status: 'ready', segments } }) }));
vi.mock('../moments/queries', () => ({ useSavePassage: () => ({}) }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({}) }));
let resize: () => void;
let height: number;
let rowHeight: number;
const disconnect = vi.fn();

beforeEach(() => {
  height = 200;
  rowHeight = 40;
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback: () => void) { resize = callback; }
    observe() {}
    disconnect = disconnect;
  });
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function (this: HTMLElement) {
    return this.getAttribute('role') === 'region' ? height : 0;
  });
  vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(1200);
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function (this: HTMLElement) {
    return this.tagName === 'LI' ? rowHeight : 0;
  });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const container = this.closest('[role="region"]');
    const index = this.tagName === 'LI' ? Array.from(this.parentElement!.children).indexOf(this) : 0;
    return { top: 160 + index * rowHeight - (this.tagName === 'LI' ? container!.scrollTop : 0) } as DOMRect;
  });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function setup(playhead = 100) {
  const onSeek = vi.fn();
  const props = { videoId: 'abc123DEF45', signedIn: false, onSeek };
  const view = render(<TranscriptPanel {...props} playhead={playhead} />);
  return { ...view, onSeek, container: screen.getByRole('region', { name: 'Transcript lines' }),
    seek: (seconds: number) => view.rerender(<TranscriptPanel {...props} playhead={seconds} />) };
}

describe('transcript auto-follow', () => {
  it('centers in the transcript container and follows forward and backward seeks without scrolling the page', () => {
    const { container, seek } = setup();
    expect(container.scrollTop).toBe(320);
    fireEvent.scroll(container); // A programmatic scroll must not pause follow.
    seek(180);
    expect(container.scrollTop).toBe(640);
    seek(80);
    expect(container.scrollTop).toBe(240);
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    expect(document.documentElement.scrollTop).toBe(0);
  });

  it('clamps naturally at both transcript boundaries', () => {
    const { container, seek } = setup(0);
    expect(container.scrollTop).toBe(0);
    seek(290);
    expect(container.scrollTop).toBe(1000);
  });

  it('pauses for manual scrolling and resumes with the follow control', () => {
    const { container, seek } = setup();
    container.scrollTop = 100;
    fireEvent.scroll(container);
    seek(180);
    act(() => resize());
    expect(container.scrollTop).toBe(100);
    fireEvent.click(screen.getByRole('button', { name: 'Follow playback' }));
    expect(container.scrollTop).toBe(640);
  });

  it('resumes follow when seeking from a transcript timestamp', () => {
    const { container, onSeek, seek } = setup();
    container.scrollTop = 100;
    fireEvent.scroll(container);
    fireEvent.click(screen.getByRole('button', { name: 'Play from 3:00' }));
    expect(onSeek).toHaveBeenCalledWith(180);
    seek(180);
    expect(container.scrollTop).toBe(640);
  });

  it('suspends centering during search and centers again when search clears', () => {
    const { container, seek } = setup();
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Line 2' } });
    container.scrollTop = 0;
    seek(200);
    expect(container.scrollTop).toBe(0);
    fireEvent.change(input, { target: { value: '' } });
    expect(container.scrollTop).toBe(720);
  });

  it('recenters after viewport or wrapped-line size changes and cleans up observers', () => {
    const { container, unmount } = setup();
    height = 300;
    rowHeight = 50;
    act(() => resize());
    expect(container.scrollTop).toBe(375);
    unmount();
    expect(disconnect).toHaveBeenCalled();
  });

  it('centers the current playhead when the transcript tab mounts again', () => {
    const view = setup(100);
    view.unmount();
    const { container } = setup(180);
    expect(container.scrollTop).toBe(640);
  });

  it('eases between lines without treating animation scroll events as manual scrolling', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
    let nextFrame: FrameRequestCallback = () => {};
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { nextFrame = callback; return 1; });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    vi.spyOn(performance, 'now').mockReturnValue(0);
    const { container, seek } = setup();
    seek(110);
    expect(container.scrollTop).toBe(320);
    act(() => nextFrame(120));
    expect(container.scrollTop).toBeGreaterThan(320);
    expect(container.scrollTop).toBeLessThan(360);
    fireEvent.scroll(container);
    expect(screen.queryByRole('button', { name: 'Follow playback' })).toBeNull();
    act(() => nextFrame(240));
    expect(container.scrollTop).toBe(360);
    seek(290);
    expect(container.scrollTop).toBe(1000); // Large seeks snap instead of flying through the transcript.
  });

  it('cancels an in-progress transition as soon as the user scrolls', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
    let nextFrame: FrameRequestCallback = () => {};
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { nextFrame = callback; return 1; });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    const { container, seek } = setup();
    seek(110);
    fireEvent.wheel(container, { deltaY: 50 });
    container.scrollTop = 400;
    act(() => nextFrame(performance.now() + 240));
    expect(container.scrollTop).toBe(400);
    expect(screen.getByRole('button', { name: 'Follow playback' })).toBeTruthy();
  });
});
