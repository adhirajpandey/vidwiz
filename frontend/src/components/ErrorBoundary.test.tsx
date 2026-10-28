// @vitest-environment jsdom
import { lazy, Suspense } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('keeps workspace content when an optional lazy component fails', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const Palette = lazy(() => Promise.reject(new Error('Chunk unavailable')));
  render(<ErrorBoundary><p>Workspace content</p><ErrorBoundary fallback={null}><Suspense fallback={null}><Palette /></Suspense></ErrorBoundary></ErrorBoundary>);
  await waitFor(() => expect(console.error).toHaveBeenCalled());
  expect(screen.getByText('Workspace content')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});
