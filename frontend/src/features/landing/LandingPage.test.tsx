// @vitest-environment jsdom
import { cleanup, createEvent, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import LandingPage from './LandingPage';

vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: vi.fn() }) }));
afterEach(() => { cleanup(); });

function setup() {
  const user = userEvent.setup();
  render(<HelmetProvider><MemoryRouter><LandingPage /></MemoryRouter></HelmetProvider>);
  return user;
}
const saved = () => screen.queryByText('Saved at 9:47.');

it('saves in the example with Alt+S only while the example has focus', async () => {
  const user = setup();
  await user.type(screen.getByRole('textbox', { name: 'YouTube link' }), 'sss');
  await user.keyboard('{Alt>}s{/Alt}');
  expect(saved()).toBeNull();

  await user.click(screen.getByRole('group', { name: 'Example: a video with its saved moments' }));
  await user.keyboard('s');
  expect(saved()).toBeNull();
  await user.keyboard('{Alt>}s{/Alt}');
  expect(saved()).toBeTruthy();
  expect(screen.getByRole('button', { name: /Save this moment/ }).textContent).toContain('Alt+S');
});

it('connects an invalid video link to its error', async () => {
  const user = setup();
  const input = screen.getByRole('textbox', { name: 'YouTube link' });
  await user.type(input, 'invalid');
  await user.click(screen.getByRole('button', { name: 'Ask about it' }));
  expect(input.getAttribute('aria-invalid')).toBe('true');
  expect(document.getElementById(input.getAttribute('aria-describedby')!)?.textContent).toBe('Paste a YouTube video link.');
  await user.clear(input);
  expect(input.getAttribute('aria-describedby')).toBeNull();
});

it.each([{ shiftKey: true }, { ctrlKey: true }, { metaKey: true }, { isComposing: true }, { repeat: true }, { prevented: true }])('ignores unsupported shortcut events: %j', extra => {
  setup();
  const demo = screen.getByRole('group', { name: 'Example: a video with its saved moments' });
  const event = createEvent.keyDown(demo, { key: 's', code: 'KeyS', altKey: true, ...extra });
  if ('prevented' in extra) event.preventDefault();
  fireEvent(demo, event);
  expect(saved()).toBeNull();
});
