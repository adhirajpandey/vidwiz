// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { libraryApi } from '../../api';
import LinkCard from './LinkCard';

vi.mock('../../api', () => ({ libraryApi: { list: vi.fn(), save: vi.fn() } }));
vi.mock('./VideoRow', () => ({ default: () => <div>Saved video row</div> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });
function Location() { return <output data-testid="location">{useLocation().pathname}{useLocation().search}</output>; }
function setup() {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ title: 'A useful video' }) }));
  const onAdded = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>
    <Location /><LinkCard link="https://youtu.be/aaaaaaaaaaa?t=1m30s" videoId="aaaaaaaaaaa" onClear={vi.fn()} onAdded={onAdded} />
  </MemoryRouter></QueryClientProvider>);
  return onAdded;
}
it('opens a saved video at the pasted time without saving again', async () => {
  vi.mocked(libraryApi.list).mockResolvedValue({ videos: [{ video_id: 'aaaaaaaaaaa' }] } as Awaited<ReturnType<typeof libraryApi.list>>);
  setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Open at 1:30' }));
  expect(screen.getByTestId('location').textContent).toBe('/v/aaaaaaaaaaa?t=90');
  expect(libraryApi.save).not.toHaveBeenCalled();
});
it('retries the failed Add to library action without opening the video', async () => {
  vi.mocked(libraryApi.list).mockResolvedValue({ videos: [], counts: { all: 0, with_moments: 0, with_chats: 0 }, total: 0, page: 1, per_page: 1, total_pages: 0 });
  vi.mocked(libraryApi.save).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ message: 'Saved' });
  const onAdded = setup();
  await waitFor(() => expect(screen.queryByText(/Checking your library/)).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'Add to library' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
  await waitFor(() => expect(onAdded).toHaveBeenCalledWith('aaaaaaaaaaa'));
  expect(screen.getByTestId('location').textContent).toBe('/');
});
it('does not claim the video is new when membership cannot be checked', async () => {
  vi.mocked(libraryApi.list).mockRejectedValue(new Error('offline'));
  setup();
  expect(await screen.findByText(/Couldn’t check your library/)).toBeTruthy();
  expect(screen.queryByText(/Not in your library yet/)).toBeNull();
});
