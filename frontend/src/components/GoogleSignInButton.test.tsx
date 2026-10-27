// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import GoogleSignInButton from './GoogleSignInButton';

vi.mock('../config', () => ({ default: { GOOGLE_CLIENT_ID: 'test-client' } }));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  delete window.google;
  document.querySelectorAll('script').forEach(script => script.remove());
  document.documentElement.classList.remove('dark');
});
function client() {
  const id = { initialize: vi.fn<(options: { callback: (response: { credential: string }) => void }) => void>(), renderButton: vi.fn((element: HTMLElement) => {
    const button = document.createElement('button');
    button.textContent = 'Continue with Google';
    element.appendChild(button);
  }) };
  window.google = { accounts: { id } };
  return id;
}
it('renders the actual provider control visibly and initializes once across rerenders and mounts', () => {
  const sdk = client();
  const success = vi.fn();
  const view = render(<GoogleSignInButton onSuccess={success} onError={vi.fn()} />);
  expect(screen.getByRole('button', { name: 'Continue with Google' }).closest('[aria-hidden="true"]')).toBeNull();
  const next = vi.fn();
  view.rerender(<GoogleSignInButton onSuccess={next} onError={vi.fn()} />);
  const callback = sdk.initialize.mock.calls[0][0].callback;
  callback({ credential: 'example' });
  expect(next).toHaveBeenCalledWith('example');
  expect(success).not.toHaveBeenCalled();
  view.unmount();
  callback({ credential: 'after-unmount' });
  expect(next).toHaveBeenCalledTimes(1);
  render(<GoogleSignInButton onSuccess={success} onError={vi.fn()} />);
  expect(sdk.initialize).toHaveBeenCalledTimes(1);
});
it('times out, ignores late loads, and lets Retry use the now available SDK', () => {
  vi.useFakeTimers();
  render(<GoogleSignInButton onSuccess={vi.fn()} onError={vi.fn()} />);
  act(() => vi.advanceTimersByTime(4999));
  expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  act(() => vi.advanceTimersByTime(1));
  const sdk = client();
  fireEvent.load(document.querySelector('script')!);
  expect(sdk.renderButton).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeTruthy();
  expect(screen.queryByText(/unavailable/)).toBeNull();
});
it('replaces a failed script on Retry and cancels timers on unmount', () => {
  vi.useFakeTimers();
  const view = render(<GoogleSignInButton onSuccess={vi.fn()} onError={vi.fn()} />);
  const first = document.querySelector('script')!;
  fireEvent.error(first);
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(document.querySelector('script')).not.toBe(first);
  expect(screen.getByRole('status').textContent).toContain('Loading');
  view.unmount();
  const sdk = client();
  fireEvent.load(document.querySelector('script')!);
  act(() => vi.advanceTimersByTime(6000));
  expect(sdk.initialize).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});
it('keeps the light rectangular provider button in both app themes', async () => {
  const sdk = client();
  render(<GoogleSignInButton onSuccess={vi.fn()} onError={vi.fn()} />);
  expect(sdk.renderButton).toHaveBeenLastCalledWith(expect.any(HTMLElement), expect.objectContaining({ theme: 'outline', shape: 'rectangular' }));
  await act(async () => document.documentElement.classList.add('dark'));
  expect(sdk.renderButton).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Continue with Google' }).parentElement?.style.colorScheme).toBe('light');
  expect(sdk.initialize).toHaveBeenCalledTimes(1);
});
