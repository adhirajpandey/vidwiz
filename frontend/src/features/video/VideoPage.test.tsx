// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import VideoPage from './VideoPage';

let completeChat: (id: number) => void;
vi.mock('../../hooks/useSignedIn', () => ({ useSignedIn: () => true }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({}) }));
vi.mock('./queries', () => ({ useVideo: () => ({ data: { title: 'Test video', video_id: 'abc123DEF45' } }) }));
vi.mock('../../components/PageTitle', () => ({ default: () => null }));
vi.mock('../../components/wiz/YouTubePlayer', () => ({ default: () => null }));
vi.mock('./CaptureBar', () => ({ default: () => null }));
vi.mock('./MomentsPanel', () => ({ default: () => <div>Saved moments</div> }));
vi.mock('./TranscriptPanel', () => ({ default: () => <div>Transcript text</div> }));
vi.mock('./OverviewPanel', () => ({ default: () => null }));
vi.mock('./AskPanel', () => ({ default: ({ onConversation }: { onConversation: (id: number) => void }) => {
  completeChat = onConversation;
  return <div>Chat initialized</div>;
} }));
afterEach(cleanup);

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function setup(query = '') {
  render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={[`/v/abc123DEF45${query}`]}>
      <Location /><Routes><Route path="/v/:videoId" element={<VideoPage />} /></Routes>
    </MemoryRouter>
  </QueryClientProvider>);
}
function selectTab(name: string) {
  fireEvent.mouseDown(screen.getByRole('tab', { name }), { button: 0, ctrlKey: false });
}

describe('video panel navigation', () => {
  it('opens Moments without initializing a hidden chat', () => {
    setup();
    expect(screen.getByRole('tab', { name: 'Moments' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByText('Chat initialized')).toBeNull();
  });

  it('keeps Moments selected when chat creation finishes after leaving Ask', () => {
    setup();
    selectTab('Ask');
    expect(screen.getByText('Chat initialized')).toBeTruthy();
    selectTab('Moments');
    act(() => completeChat(42));
    expect(screen.getByRole('tab', { name: 'Moments' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('location').textContent).toBe('?tab=moments&c=42');
    expect(screen.getByText('Chat initialized')).toBeTruthy();
  });

  it('opens Ask for a conversation link but honors an explicit panel', () => {
    setup('?c=42');
    expect(screen.getByRole('tab', { name: 'Ask' }).getAttribute('aria-selected')).toBe('true');
    cleanup();
    setup('?c=42&tab=transcript');
    expect(screen.getByRole('tab', { name: 'Transcript' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByText('Chat initialized')).toBeNull();
  });
});
