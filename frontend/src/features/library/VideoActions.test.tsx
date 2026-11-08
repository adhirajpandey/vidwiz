// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { libraryApi } from '../../api';
import type { LibraryVideo } from '../../api';
import VideoActions from './VideoActions';

const success = vi.hoisted(() => vi.fn());

vi.mock('../../api', () => ({ libraryApi: { remove: vi.fn() }, momentsApi: {} }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ success, error: vi.fn() }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function setup(counts: Pick<LibraryVideo, 'moment_count' | 'chat_count'>) {
  const user = userEvent.setup();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <VideoActions video={{ video_id: 'aaaaaaaaaaa', ...counts } as LibraryVideo} />
  </QueryClientProvider>);
  return user;
}

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Video actions' }));
  await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
  await screen.findByRole('dialog');
}

it('states what will be deleted and waits for confirmation', async () => {
  vi.mocked(libraryApi.remove).mockResolvedValue({ message: 'Removed' });
  const user = setup({ moment_count: 4, chat_count: 1 });
  await openDialog(user);
  expect(screen.getByText("This permanently deletes your 4 moments and 1 chat for this video. You can't undo this.")).toBeTruthy();
  expect(libraryApi.remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(libraryApi.remove).toHaveBeenCalledWith('aaaaaaaaaaa'));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(success).toHaveBeenCalledWith('Video deleted');
});

it('uses plain copy for a video with no moments or chats', async () => {
  const user = setup({ moment_count: 0, chat_count: 0 });
  await openDialog(user);
  expect(screen.getByText('This removes the video from your library.')).toBeTruthy();
});

it('starts on Cancel and restores focus when dismissed', async () => {
  const user = setup({ moment_count: 1, chat_count: 0 });
  await openDialog(user);
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' })));
  await user.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Video actions' }));
  expect(libraryApi.remove).not.toHaveBeenCalled();
});

it('keeps the dialog open after a failed delete so it can be retried', async () => {
  vi.mocked(libraryApi.remove).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ message: 'Removed' });
  const user = setup({ moment_count: 1, chat_count: 0 });
  await openDialog(user);
  await user.click(screen.getByRole('button', { name: 'Delete' }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.getByRole('dialog')).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});
