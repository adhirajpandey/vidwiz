// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import LandingPage from './LandingPage';

const createConversation = vi.fn();
vi.mock('../../api', () => ({ conversationsApi: { createConversation: (...args: unknown[]) => createConversation(...args) } }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: vi.fn() }) }));

beforeAll(() => {
  // jsdom has no modal dialogs.
  HTMLDialogElement.prototype.showModal = function showModal() { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function close() { this.removeAttribute('open'); this.dispatchEvent(new Event('close')); };
});
afterEach(() => { cleanup(); createConversation.mockReset(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function setup() {
  const user = userEvent.setup();
  render(
    <HelmetProvider>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/v/:videoId" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </HelmetProvider>,
  );
  return user;
}

it('connects an invalid video link to its error', async () => {
  const user = setup();
  const input = screen.getByRole('textbox', { name: 'YouTube video link' });
  await user.type(input, 'invalid');
  await user.click(screen.getByRole('button', { name: 'Ask about it' }));
  expect(input.getAttribute('aria-invalid')).toBe('true');
  expect(document.getElementById(input.getAttribute('aria-describedby')!)?.textContent).toBe('Enter a valid YouTube video link.');
  expect(createConversation).not.toHaveBeenCalled();
  await user.clear(input);
  expect(document.getElementById(input.getAttribute('aria-describedby')!)?.textContent).toBe('No account needed to try it.');
});

it('opens Ask on a pasted video as a guest, keeping its start time', async () => {
  createConversation.mockResolvedValue({ id: 7 });
  const user = setup();
  await user.type(screen.getByRole('textbox', { name: 'YouTube video link' }), 'https://youtu.be/N4YjXJVzoZY?t=2m13s');
  await user.click(screen.getByRole('button', { name: 'Ask about it' }));
  expect(createConversation).toHaveBeenCalledWith({ scope: 'video', video_id: 'N4YjXJVzoZY' });
  expect(sessionStorage.getItem('guestSessionId')).toBeTruthy();
  expect((await screen.findByTestId('where')).textContent).toBe('/v/N4YjXJVzoZY?tab=ask&c=7&t=133');
});

it('plays a cited source from the cited second, and closing removes the player', async () => {
  const user = setup();
  await user.click(screen.getByRole('button', { name: /16:17\s*Zettelkasten Smart Notes/ }));
  const frame = screen.getByTitle('Source video');
  expect(frame.getAttribute('src')).toContain('/embed/ziE6UExsOrs?start=977');
  expect(screen.getByRole('link', { name: 'Open in VidWiz' }).getAttribute('href')).toBe('/v/ziE6UExsOrs?t=977');
  document.querySelector('dialog')!.close();
  expect(await screen.findByRole('button', { name: /4:35\s*Mini Essays/ })).toBeTruthy();
  expect(screen.queryByTitle('Source video')).toBeNull();
});

it('switches the recording beside the ways to save, starting with the extension', async () => {
  const user = setup();
  const computer = screen.getByRole('button', { name: 'Show saving on your computer' });
  const phone = screen.getByRole('button', { name: 'Show saving on your phone' });
  const places = within(document.querySelector<HTMLElement>('.places')!);
  expect(computer.getAttribute('aria-pressed')).toBe('true');
  // A wide cut for computers and a tall one for phones; CSS shows one.
  expect(places.getAllByRole('button', { name: /Alt\+S saves the moment at 14:19/ })).toHaveLength(2);
  await user.click(phone);
  expect(phone.getAttribute('aria-pressed')).toBe('true');
  expect(computer.getAttribute('aria-pressed')).toBe('false');
  expect(places.queryByRole('button', { name: /Alt\+S saves the moment at 14:19/ })).toBeNull();
  expect(places.getByRole('button', { name: /Tapping Save keeps the moment at 0:42/ })).toBeTruthy();
});

function playbackSetup(reducedMotion = false, withoutObserver = false) {
  const callbacks = new Map<Element, (entry: { isIntersecting: boolean; intersectionRatio: number }) => void>();
  vi.stubGlobal('IntersectionObserver', class {
    callback: (entries: unknown[]) => void;
    constructor(callback: (entries: unknown[]) => void) { this.callback = callback; }
    observe(target: Element) { callbacks.set(target, entry => this.callback([entry])); }
    disconnect() {}
  });
  if (withoutObserver) vi.stubGlobal('IntersectionObserver', undefined);
  vi.stubGlobal('matchMedia', () => ({ matches: reducedMotion }));
  vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  const frames = new Map<number, FrameRequestCallback>();
  let id = 0;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.set(++id, callback); return id; });
  vi.stubGlobal('cancelAnimationFrame', (key: number) => frames.delete(key));
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  const pause = vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  setup();
  const box = document.querySelector<HTMLElement>('.stage .only-phone .screen')!;
  const video = box.querySelector('video')!;
  const intersect = (visible: boolean) => act(() => callbacks.get(box)!({ isIntersecting: visible, intersectionRatio: visible ? 0.5 : 0 }));
  const loaded = async () => {
    await act(async () => { window.dispatchEvent(new Event('load')); });
    for (let i = 0; i < 2; i++) {
      await act(async () => {
        const pending = [...frames.values()]; frames.clear();
        pending.forEach(callback => callback(0));
      });
    }
  };
  return { box, video, play, pause, intersect, loaded };
}

it('waits for initial load and paint before muted inline autoplay, then pauses offscreen', async () => {
  const { box, video, play, pause, intersect, loaded } = playbackSetup();
  intersect(true);
  expect(video.getAttribute('src')).toBeNull();
  expect(play).not.toHaveBeenCalled();
  await loaded();
  expect(video.src).toContain('save-phone.mp4');
  expect(video.muted).toBe(true);
  expect(video.playsInline).toBe(true);
  expect(play).toHaveBeenCalledTimes(1);
  expect(box.querySelector('.clip-poster.played')).toBeNull();
  fireEvent.playing(video);
  expect(box.querySelector('.clip-poster.played')).not.toBeNull();
  pause.mockClear();
  intersect(false);
  expect(pause).toHaveBeenCalledTimes(1);
});

it('keeps the poster and allows a tap when Safari rejects autoplay', async () => {
  const { box, video, play, intersect, loaded } = playbackSetup();
  play.mockRejectedValue(new DOMException('Autoplay blocked', 'NotAllowedError'));
  intersect(true);
  await loaded();
  expect(box.querySelector('.clip-poster.played')).toBeNull();
  expect(box.classList.contains('play-blocked')).toBe(true);
  expect(box.getAttribute('aria-label')).toContain('Press to play');
  play.mockResolvedValue();
  fireEvent.click(box);
  expect(play).toHaveBeenCalledTimes(2);
  fireEvent.playing(video);
  expect(box.classList.contains('play-blocked')).toBe(false);
  expect(video.muted).toBe(true);
});

it('does not fetch video for reduced motion until a tap', async () => {
  const { box, video, play, intersect, loaded } = playbackSetup(true);
  intersect(true);
  await loaded();
  expect(video.getAttribute('src')).toBeNull();
  expect(play).not.toHaveBeenCalled();
  fireEvent.click(box);
  expect(play).toHaveBeenCalledTimes(1);
});

it('does not start a video that scrolled away before initial load completed', async () => {
  const { video, play, intersect, loaded } = playbackSetup();
  intersect(true);
  intersect(false);
  await loaded();
  expect(video.getAttribute('src')).toBeNull();
  expect(play).not.toHaveBeenCalled();
});

it('updates playback and removes the poster without IntersectionObserver', () => {
  const { box, video, play } = playbackSetup(false, true);
  fireEvent.click(box);
  expect(play).toHaveBeenCalledTimes(1);
  fireEvent.play(video);
  fireEvent.playing(video);
  expect(box.querySelector('.clip-poster.played')).not.toBeNull();
  expect(box.getAttribute('aria-label')).toContain('Press to pause');
  fireEvent.pause(video);
  expect(box.getAttribute('aria-label')).toContain('Press to play');
});

it('checks viewport visibility for autoplay without IntersectionObserver', async () => {
  const { box, play, pause, loaded } = playbackSetup(false, true);
  vi.spyOn(box, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100, x: 0, y: 0, toJSON() {} });
  fireEvent.scroll(window);
  await loaded();
  expect(play).toHaveBeenCalledTimes(1);
  pause.mockClear();
  vi.mocked(box.getBoundingClientRect).mockReturnValue({ left: 0, top: -200, right: 100, bottom: -100, width: 100, height: 100, x: 0, y: -200, toJSON() {} });
  fireEvent.scroll(window);
  expect(pause).toHaveBeenCalled();
});
