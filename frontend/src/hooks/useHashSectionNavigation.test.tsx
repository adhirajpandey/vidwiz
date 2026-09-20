// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { useHashSectionNavigation } from './useHashSectionNavigation';

function Harness({ ready }: { ready: boolean }) {
  const navigate = useNavigate();
  useHashSectionNavigation('credits', ready);
  return (
    <>
      <button onClick={() => navigate('/profile#credits')}>Go to credits</button>
      <section id="credits" tabIndex={-1}>Credit packs</section>
    </>
  );
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => {
    callback(0);
    return 1;
  });
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('useHashSectionNavigation', () => {
  it('waits for content before scrolling and focusing the requested section', async () => {
    const rendered = render(
      <MemoryRouter initialEntries={['/profile#credits']}>
        <Harness ready={false} />
      </MemoryRouter>,
    );
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    rendered.rerender(
      <MemoryRouter initialEntries={['/profile#credits']}>
        <Harness ready />
      </MemoryRouter>,
    );
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' }));
    expect(document.activeElement).toBe(screen.getByText('Credit packs'));
  });

  it('handles hash navigation while already on the profile page', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/profile']}>
        <Harness ready />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: 'Go to credits' }));
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());
    expect(document.activeElement).toBe(screen.getByText('Credit packs'));
  });
});
