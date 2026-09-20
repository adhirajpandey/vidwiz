// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { authApi } from '../../api';
import { getUserFromToken } from '../../lib/authUtils';
import Navbar from './Navbar';

vi.mock('../../api', () => ({ authApi: { getMe: vi.fn() } }));
vi.mock('../../lib/authUtils', () => ({
  getUserFromToken: vi.fn(),
  removeToken: vi.fn(),
}));

function Location() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.hash}</output>;
}

function renderNavbar() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Navbar />
      <Routes><Route path="*" element={<Location />} /></Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getUserFromToken).mockReturnValue({ email: 'long.account.name@example.com', name: 'A very long account name' });
  vi.mocked(authApi.getMe).mockResolvedValue({ credits_balance: 1234567 } as never);
});
afterEach(cleanup);

describe('Navbar credits menu', () => {
  it('loads, formats, and links the balance to the profile credit section', async () => {
    const user = userEvent.setup();
    let resolveProfile!: (value: { credits_balance: number }) => void;
    vi.mocked(authApi.getMe).mockReturnValueOnce(new Promise(resolve => { resolveProfile = resolve; }) as never);
    renderNavbar();
    const trigger = screen.getByRole('button', { name: 'User menu' });
    await user.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByLabelText('Loading credit balance')).toBeTruthy();
    await act(async () => resolveProfile({ credits_balance: 1234567 }));
    await waitFor(() => expect(screen.getByText((1234567).toLocaleString())).toBeTruthy());
    await user.click(screen.getByRole('link', { name: /Credits/ }));
    expect(screen.getByTestId('location').textContent).toBe('/profile#credits');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('shows an independent retry action and restores trigger focus on Escape', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.getMe)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ credits_balance: 0 } as never);
    renderNavbar();
    const trigger = screen.getByRole('button', { name: 'User menu' });
    await user.click(trigger);
    await waitFor(() => expect(screen.getByText('Unavailable')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: 'Retry loading credit balance' }));
    await waitFor(() => expect(screen.getByText('0')).toBeTruthy());
    await user.keyboard('{Escape}');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('does not request a balance for guests', () => {
    vi.mocked(getUserFromToken).mockReturnValue(null);
    renderNavbar();
    expect(screen.queryByRole('button', { name: 'User menu' })).toBeNull();
    expect(authApi.getMe).not.toHaveBeenCalled();
  });
});
