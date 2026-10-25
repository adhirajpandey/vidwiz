// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { authApi } from '../../api';
import type { ApiTokenRead } from '../../api';
import TokensSection from './TokensSection';

const notifyError = vi.fn();
vi.mock('../../api', () => ({ authApi: { listTokens: vi.fn(), revokeToken: vi.fn(), createToken: vi.fn() } }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: notifyError }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const token = { id: 7, name: 'Phone', token_hint: 'ab12', created_at: '2026-10-01T00:00:00Z', last_used_at: null } as ApiTokenRead;
function setup() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><TokensSection /></QueryClientProvider>);
  return userEvent.setup();
}

it('asks before revoking, returns focus on Escape, and revokes on confirm', async () => {
  vi.mocked(authApi.listTokens).mockResolvedValue([token]);
  vi.mocked(authApi.revokeToken).mockResolvedValue(undefined as never);
  const user = setup();
  await user.click(await screen.findByRole('button', { name: 'Revoke Phone' }));
  expect(authApi.revokeToken).not.toHaveBeenCalled();
  expect(document.activeElement?.textContent).toBe('Revoke');
  await user.keyboard('{Escape}');
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Revoke Phone' })));
  await user.click(screen.getByRole('button', { name: 'Revoke Phone' }));
  await user.click(screen.getByRole('button', { name: 'Revoke' }));
  await waitFor(() => expect(authApi.revokeToken).toHaveBeenCalledWith(7));
});

it('tells failed loading apart from an empty list and retries', async () => {
  vi.mocked(authApi.listTokens).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([]);
  const user = setup();
  await user.click(await screen.findByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('No tokens yet.')).toBeTruthy();
});

it('keeps each pending revoke confirmed and disabled until it settles', async () => {
  const other = { ...token, id: 8, name: 'Tablet' };
  vi.mocked(authApi.listTokens).mockResolvedValue([token, other]);
  vi.mocked(authApi.revokeToken).mockReturnValue(new Promise(() => {}));
  const user = setup();
  await user.click(await screen.findByRole('button', { name: 'Revoke Phone' }));
  await user.click(screen.getByRole('button', { name: 'Revoke' }));
  await user.click(screen.getByRole('button', { name: 'Revoke Tablet' }));
  await user.click(within(screen.getByRole('group', { name: 'Revoke Tablet' })).getByRole('button', { name: 'Revoke' }));
  await waitFor(() => expect(authApi.revokeToken).toHaveBeenCalledWith(8));
  const phone = screen.getByRole('group', { name: 'Revoke Phone' });
  expect((within(phone).getByRole('button', { name: 'Revoke' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.keyDown(phone, { key: 'Escape' });
  expect(screen.getByRole('group', { name: 'Revoke Phone' })).toBeTruthy();
});
