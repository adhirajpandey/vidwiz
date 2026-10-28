// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
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
afterEach(() => { cleanup(); createConversation.mockReset(); sessionStorage.clear(); });

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
