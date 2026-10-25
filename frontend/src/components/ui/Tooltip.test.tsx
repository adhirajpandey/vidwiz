// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Tooltip } from './Tooltip';

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function setup() {
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<><button type="button">Before</button><Tooltip label="Edit note or delete"><button type="button" aria-label="Moment actions">…</button></Tooltip></>);
  return user;
}

it('shows at once on keyboard focus and closes on Escape', async () => {
  const user = setup();
  await user.tab();
  await user.tab();
  expect(screen.getByRole('tooltip').textContent).toBe('Edit note or delete');
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).toBeNull();
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Moment actions' }));
});

it('waits for a short hover', async () => {
  const user = setup();
  await user.hover(screen.getByRole('button', { name: 'Moment actions' }));
  expect(screen.queryByRole('tooltip')).toBeNull();
  await act(async () => { vi.advanceTimersByTime(400); });
  expect(screen.getByRole('tooltip').textContent).toBe('Edit note or delete');
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).toBeNull();
});
