// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Toast from './Toast';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

it('announces confirmations politely and errors assertively', () => {
  render(<><Toast id={1} title="Saved" message="" type="success" onClose={() => {}} /><Toast id={2} title="Failed" message="" type="error" onClose={() => {}} /></>);
  expect(screen.getByRole('status').textContent).toContain('Saved');
  expect(screen.getByRole('alert').textContent).toContain('Failed');
});

it('pauses its countdown while hovered or focused and resumes afterwards', () => {
  const onClose = vi.fn();
  render(<Toast id={1} title="Saved" message="" type="success" action={{ label: 'View moment', onClick: () => {} }} onClose={onClose} />);
  const toast = screen.getByRole('status');
  act(() => { vi.advanceTimersByTime(3000); });
  fireEvent.mouseEnter(toast);
  act(() => { vi.advanceTimersByTime(10_000); });
  fireEvent.mouseLeave(toast);
  act(() => { screen.getByRole('button', { name: 'View moment' }).focus(); });
  act(() => { vi.advanceTimersByTime(10_000); });
  expect(onClose).not.toHaveBeenCalled();
  act(() => { screen.getByRole('button', { name: 'View moment' }).blur(); });
  act(() => { vi.advanceTimersByTime(1300); });
  expect(onClose).toHaveBeenCalledWith(1);
});
