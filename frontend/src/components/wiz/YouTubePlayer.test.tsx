// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import YouTubePlayer from './YouTubePlayer';
import type { PlayerOptions, YouTubePlayerHandle } from './YouTubePlayer';

let options: PlayerOptions;
let instances: { seekTo: ReturnType<typeof vi.fn>; playVideo: ReturnType<typeof vi.fn>; getPlayerState: ReturnType<typeof vi.fn>; destroy: ReturnType<typeof vi.fn> }[];
beforeEach(() => {
  vi.useFakeTimers();
  instances = [];
  window.YT = { Player: class {
    seekTo = vi.fn(); playVideo = vi.fn(); getPlayerState = vi.fn(() => 2); destroy = vi.fn();
    constructor(_element: HTMLElement, value: PlayerOptions) { options = value; instances.push(this); }
  } };
  Element.prototype.scrollIntoView = vi.fn();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});
afterEach(() => { cleanup(); delete window.YT; vi.useRealTimers(); vi.restoreAllMocks(); });

async function setup() {
  const ref = createRef<YouTubePlayerHandle>();
  const view = render(<YouTubePlayer ref={ref} videoId="abc123DEF45" />);
  await act(async () => {});
  return { ref, view, player: instances[0] };
}

describe('YouTube Watch behavior', () => {
  it('queues only the latest click until ready, then seeks with lead-in and plays', async () => {
    const { ref, player } = await setup();
    act(() => { ref.current!.watch(83); ref.current!.watch(200); });
    expect(player.seekTo).not.toHaveBeenCalled();
    act(() => options.events.onReady());
    expect(player.seekTo).toHaveBeenCalledExactlyOnceWith(198, true);
    expect(player.playVideo).toHaveBeenCalledOnce();
    act(() => options.events.onStateChange({ data: 1 }));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.queryByRole('status')).toBeNull();
    act(() => ref.current!.watch(1));
    expect(player.seekTo).toHaveBeenLastCalledWith(0, true);
    expect(player.playVideo).toHaveBeenCalledTimes(2);
  });

  it('does not time out when already playing and does not stop at passage end', async () => {
    const { ref, player } = await setup();
    act(() => options.events.onReady());
    player.getPlayerState.mockReturnValue(1);
    act(() => ref.current!.watch(30));
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.queryByRole('status')).toBeNull();
    expect(player.destroy).not.toHaveBeenCalled();
  });

  it('times out an unready player without playing a stale request later', async () => {
    const { ref, player } = await setup();
    act(() => ref.current!.watch(83));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByRole('link', { name: 'Open on YouTube' }).getAttribute('href')).toContain('t=81s');
    act(() => options.events.onReady());
    expect(player.playVideo).not.toHaveBeenCalled();
  });

  it('shows a Play prompt for blocked autoplay and a link for player errors', async () => {
    const { ref } = await setup();
    act(() => options.events.onReady());
    act(() => ref.current!.watch(83));
    act(() => options.events.onAutoplayBlocked());
    expect(screen.getByRole('status').textContent).toContain('Press Play');
    act(() => options.events.onError());
    expect(screen.getByRole('status').textContent).toContain('unavailable');
    expect(screen.getByRole('link').getAttribute('href')).toContain('t=81s');
  });

  it('discards pending requests and callbacks when changing videos or unmounting', async () => {
    const { ref, view, player } = await setup();
    act(() => ref.current!.watch(83));
    const stale = options.events;
    view.rerender(<YouTubePlayer ref={ref} videoId="xyz123DEF45" />);
    await act(async () => {});
    act(() => stale.onReady());
    expect(player.playVideo).not.toHaveBeenCalled();
    expect(player.destroy).toHaveBeenCalledOnce();
    act(() => options.events.onReady());
    expect(instances[1].playVideo).not.toHaveBeenCalled();
    view.unmount();
    act(() => { options.events.onAutoplayBlocked(); vi.advanceTimersByTime(10_000); });
    expect(instances[1].destroy).toHaveBeenCalledOnce();
  });

  it('scrolls only an off-screen player and respects reduced motion', async () => {
    const { ref } = await setup();
    act(() => ref.current!.watch(10));
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({ top: -10, bottom: 200 } as DOMRect);
    vi.mocked(window.matchMedia).mockReturnValue({ matches: true } as MediaQueryList);
    act(() => ref.current!.watch(20));
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'center' });
  });

  it('shows a timed fallback when playback throws or fails to start after readiness', async () => {
    const { ref, player } = await setup();
    act(() => options.events.onReady());
    act(() => ref.current!.watch(20));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByRole('status').textContent).toContain('Playback did not start');
    player.playVideo.mockImplementation(() => { throw new Error('player unavailable'); });
    act(() => ref.current!.watch(40));
    expect(screen.getByRole('status').textContent).toContain('Playback could not start');
    expect(screen.getByRole('link').getAttribute('href')).toContain('t=38s');
  });

  it('offers YouTube when the API script cannot load', async () => {
    delete window.YT;
    const { ref } = await setup();
    act(() => ref.current!.watch(83));
    const script = document.querySelector('script[src="https://www.youtube.com/iframe_api"]')!;
    await act(async () => script.dispatchEvent(new Event('error')));
    expect(screen.getByRole('status').textContent).toContain('could not load');
    expect(screen.getByRole('link').getAttribute('href')).toContain('t=81s');
    delete window.onYouTubeIframeAPIReady;
  });
});
