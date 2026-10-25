// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import SearchForm from './SearchForm';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it.each([['MacIntel', '⌘K'], ['iPad', '⌘K'], ['Win32', 'Ctrl K'], ['Linux x86_64', 'Ctrl K']])('shows the palette shortcut for %s', (platform, label) => {
  vi.spyOn(navigator, 'platform', 'get').mockReturnValue(platform);
  render(<MemoryRouter><SearchForm shortcut /></MemoryRouter>);
  expect(screen.getByText(label).tagName).toBe('KBD');
});
