// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import LibraryPage from './LibraryPage';

const empty = (total_pages: number) => ({ videos: [], total: 0, counts: { all: 0, with_moments: 0, with_chats: 0 }, total_pages });
const library = vi.hoisted(() => ({ current: {} as { data: unknown; isFetching?: boolean } }));
library.current = { data: empty(0) };
vi.mock('./queries', () => ({ useLibrary: () => library.current }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: vi.fn() }) }));
vi.mock('../../components/PageTitle', () => ({ default: () => null }));
afterEach(() => { cleanup(); vi.useRealTimers(); library.current = { data: empty(0) }; });
function Navigation() {
  const navigate = useNavigate();
  return <><output data-testid="query">{useLocation().search}</output><button onClick={() => navigate('?q=other')}>Other search</button><button onClick={() => navigate(-1)}>Back</button></>;
}
it('preserves a trailing space across debounce while still following navigation', async () => {
  vi.useFakeTimers();
  render(<MemoryRouter><Navigation /><LibraryPage /></MemoryRouter>);
  const input = screen.getByRole('textbox') as HTMLInputElement;
  fireEvent.change(input, { target: { value: 'foo ' } });
  await act(async () => { vi.advanceTimersByTime(300); });
  expect(screen.getByTestId('query').textContent).toBe('?q=foo');
  expect(input.value).toBe('foo ');
  fireEvent.change(input, { target: { value: `${input.value}bar` } });
  await act(async () => { vi.advanceTimersByTime(300); });
  expect(input.value).toBe('foo bar');
  expect(screen.getByTestId('query').textContent).toBe('?q=foo+bar');
  fireEvent.click(screen.getByText('Other search'));
  expect(input.value).toBe('other');
  fireEvent.click(screen.getByText('Back'));
  expect(input.value).toBe('foo bar');
  fireEvent.change(input, { target: { value: '' } });
  await act(async () => { vi.advanceTimersByTime(300); });
  expect(screen.getByTestId('query').textContent).toBe('');
});

it('moves to the last page only once the page count is current', async () => {
  const page = () => <MemoryRouter initialEntries={['/library?page=2']}><Navigation /><LibraryPage /></MemoryRouter>;
  // Cached data for this page can hold an old, smaller count until the refetch ends.
  library.current = { data: empty(1), isFetching: true };
  const { rerender } = render(page());
  expect(screen.getByTestId('query').textContent).toBe('?page=2');
  library.current = { data: empty(1), isFetching: false };
  rerender(page());
  await waitFor(() => expect(screen.getByTestId('query').textContent).toBe(''));
});
