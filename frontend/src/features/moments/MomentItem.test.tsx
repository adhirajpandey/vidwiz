// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { momentsApi } from '../../api';
import type { MomentRead } from '../../api';
import MomentItem from './MomentItem';
import { setActiveRow } from './rowFocus';

vi.mock('../../api', () => ({ momentsApi: { remove: vi.fn(), update: vi.fn() } }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: vi.fn() }) }));
vi.mock('./MomentStatus', () => ({ default: () => null }));
afterEach(() => { cleanup(); setActiveRow(null); vi.clearAllMocks(); });
function setup() {
  const user = userEvent.setup();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><MemoryRouter><ul>
    {[1, 2].map(id => <MomentItem key={id} moment={{ id, video_id: 'aaaaaaaaaaa', at_seconds: id * 10, note: `Note ${id}`, ai_status: 'not_requested', resolve_status: 'resolved' } as MomentRead} />)}
  </ul></MemoryRouter></QueryClientProvider>);
  return user;
}

it('confirms before deleting, focuses Delete, and restores focus on Escape', async () => {
  const user = setup();
  const actions = screen.getAllByRole('button', { name: 'Moment actions' })[0];
  await user.click(actions);
  await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
  expect(momentsApi.remove).not.toHaveBeenCalled();
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Delete' })));
  await user.keyboard('{Escape}');
  expect(screen.queryByText('Delete this moment?')).toBeNull();
  expect(document.activeElement).toBe(actions);
});

it('allows only one active row and keeps a failed delete available to retry', async () => {
  vi.mocked(momentsApi.remove).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ message: 'Saved' });
  const user = setup();
  const actions = screen.getAllByRole('button', { name: 'Moment actions' });
  await user.click(actions[0]);
  await user.click(screen.getByRole('menuitem', { name: 'Edit note' }));
  expect(screen.getByRole('textbox')).toBeTruthy();
  await user.click(actions[1]);
  await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
  expect(screen.queryByRole('textbox')).toBeNull();
  expect(screen.getAllByText('Delete this moment?')).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: 'Delete' }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(momentsApi.remove).toHaveBeenCalledWith(2);
  await user.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(screen.queryByText('Delete this moment?')).toBeNull());
});

it('keeps a newer delete confirmation and its focus when a pending note save finishes', async () => {
  let finish!: (value: MomentRead) => void;
  vi.mocked(momentsApi.update).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const user = setup();
  const actions = screen.getAllByRole('button', { name: 'Moment actions' })[0];
  await user.click(actions);
  await user.click(screen.getByRole('menuitem', { name: 'Edit note' }));
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await user.click(actions);
  await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
  const deleteButton = screen.getByRole('button', { name: 'Delete' });
  await waitFor(() => expect(document.activeElement).toBe(deleteButton));
  await act(async () => finish({ id: 1 } as MomentRead));
  expect(screen.getByText('Delete this moment?')).toBeTruthy();
  expect(document.activeElement).toBe(deleteButton);
});
