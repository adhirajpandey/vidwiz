// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { momentsApi } from '../../api';
import CaptureBar from './CaptureBar';

const success = vi.fn();
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ success, error: vi.fn() }) }));
vi.mock('../../hooks/useProfile', () => ({ PROFILE_KEY: ['profile'], useProfile: () => ({ data: { ai_moments_default: true, credits_balance: 0 } }) }));
vi.mock('../../api', () => ({ momentsApi: { capture: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function renderCapture() {
  vi.mocked(momentsApi.capture).mockResolvedValue({ moment: { id: 42 }, merged: false } as Awaited<ReturnType<typeof momentsApi.capture>>);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><CaptureBar videoId="aaaaaaaaaaa" playhead={20} currentTime={() => 20} /></MemoryRouter></QueryClientProvider>);
}

it('captures with Alt+S using the default and ignores old shortcuts and repeated keys', async () => {
  renderCapture();
  for (const key of [{ key: 's' }, { key: 'S', shiftKey: true }, { key: 's', altKey: true, shiftKey: true }, { key: 's', altKey: true, repeat: true }]) {
    fireEvent.keyDown(document.body, key);
  }
  expect(momentsApi.capture).not.toHaveBeenCalled();
  await act(async () => fireEvent.keyDown(document.body, { key: 'ß', code: 'KeyS', altKey: true }));
  expect(momentsApi.capture).toHaveBeenCalledExactlyOnceWith({ video: 'aaaaaaaaaaa', at: 20, note: null, ai: true, source: 'web' });
});

it('saves multiline notes on Enter and ignores shortcuts while typing and composing', async () => {
  renderCapture();
  fireEvent.click(screen.getByRole('button', { name: 'Add note' }));
  const field = screen.getByRole('textbox');
  fireEvent.change(field, { target: { value: 'First line\nSecond line' } });
  fireEvent.keyDown(field, { key: 's', altKey: true });
  fireEvent.keyDown(field, { key: 'Enter', shiftKey: true });
  fireEvent.keyDown(field, { key: 'Enter', isComposing: true });
  expect(momentsApi.capture).not.toHaveBeenCalled();
  await act(async () => fireEvent.keyDown(field, { key: 'Enter' }));
  expect(momentsApi.capture).toHaveBeenCalledExactlyOnceWith({ video: 'aaaaaaaaaaa', at: 20, note: 'First line\nSecond line', ai: true, source: 'web' });
});

it('starts with notes collapsed, shows the credit notice, and offers View without navigating on save', async () => {
  const onView = vi.fn();
  vi.mocked(momentsApi.capture).mockResolvedValue({ moment: { id: 42 }, merged: false } as Awaited<ReturnType<typeof momentsApi.capture>>);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><CaptureBar videoId="aaaaaaaaaaa" playhead={20} currentTime={() => 20} onView={onView} /></MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole('textbox')).toBeNull();
  expect(screen.getByRole('status').textContent).toContain('No credits left');
  fireEvent.click(screen.getByRole('button', { name: 'Add note' }));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Keep this' } });
  await act(async () => fireEvent.submit(screen.getByRole('button', { name: /Save moment/ }).closest('form')!));
  expect(momentsApi.capture).toHaveBeenCalledWith({ video: 'aaaaaaaaaaa', at: 20, note: 'Keep this', ai: true, source: 'web' });
  expect(onView).not.toHaveBeenCalled();
  const action = success.mock.calls[0][2];
  expect(action.label).toBe('View moment');
  action.onClick();
  expect(onView).toHaveBeenCalledWith(42);
  expect(screen.queryByRole('textbox')).toBeNull();
});
