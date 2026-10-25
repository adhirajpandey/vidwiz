// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { WatchPassage, WizPassageProvider } from './WizCitation';

afterEach(cleanup);
const passage = { video_id: 'abcdefghijk', start_seconds: 90, end_seconds: 100, chunk_ids: ['a'] };
it('offers a real link for a library passage, including its time', () => {
  const watch = vi.fn();
  render(<MemoryRouter><WizPassageProvider value={{ watch, watchHref: () => '/v/abcdefghijk?t=90' }}><WatchPassage passage={passage} /></WizPassageProvider></MemoryRouter>);
  const link = screen.getByRole('link', { name: /Watch/ });
  expect(link.getAttribute('href')).toBe('/v/abcdefghijk?t=90');
  expect(watch).not.toHaveBeenCalled();
});
it('seeks the current player using a button for an in-video passage', () => {
  const watch = vi.fn();
  render(<WizPassageProvider value={{ watch }}><WatchPassage passage={passage} /></WizPassageProvider>);
  fireEvent.click(screen.getByRole('button', { name: /Watch/ }));
  expect(watch).toHaveBeenCalledWith(passage);
});
