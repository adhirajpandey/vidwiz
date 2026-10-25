// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import VideoPage from './VideoPage';

let wideScreen = false;
vi.stubGlobal('matchMedia', () => ({ matches: wideScreen, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
let completeChat: (id: number) => void;
vi.mock('../../hooks/useSignedIn', () => ({ useSignedIn: () => true }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({}) }));
const loaded = { data: { title: 'Test video', video_id: 'abc123DEF45' } };
let video: Record<string, unknown> = loaded;
vi.mock('./queries', () => ({ useVideo: () => video }));
vi.mock('../../components/PageTitle', () => ({
  default: ({ title }: { title: string | string[] }) => <output data-testid="title">{[title].flat().join(' · ')}</output>,
}));
vi.mock('../../components/wiz/YouTubePlayer', () => ({ default: () => null }));
vi.mock('./CaptureBar', () => ({ default: () => null }));
vi.mock('./MomentsPanel', () => ({ default: () => <div>Saved moments</div> }));
vi.mock('./TranscriptPanel', () => ({ default: () => <div>Transcript text</div> }));
vi.mock('./OverviewPanel', () => ({ default: ({ onAsk }: { onAsk: (q: string) => void }) => <button onClick={() => onAsk('Why does this work?')}>Suggested question</button> }));
vi.mock('./AskPanel', () => ({ default: ({ onConversation, draft }: { onConversation: (id: number) => void; draft?: { text: string } }) => {
  completeChat = onConversation;
  return <div>Chat initialized{draft && <output>{draft.text}</output>}</div>;
} }));
afterEach(() => { cleanup(); video = loaded; wideScreen = false; });

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

describe('video tab title', () => {
  const title = () => screen.getByTestId('title').textContent;

  it('names the video and the open panel', () => {
    setup();
    expect(title()).toBe('Test video · Moments');
    selectTab('Transcript');
    expect(title()).toBe('Test video · Transcript');
  });

  it('says Video, never the video ID, while loading, without a title, or after a failure', () => {
    video = { data: undefined };
    setup();
    expect(title()).toBe('Video');
    cleanup();
    video = { data: { title: null, video_id: 'abc123DEF45' } };
    setup('?tab=ask');
    expect(title()).toBe('Video · Ask');
    cleanup();
    video = { isError: true, error: new Error('offline'), refetch: () => undefined };
    setup();
    expect(title()).toBe('Video');
  });
});

 it('shows moments below the player and Transcript by default on desktop', () => {
  wideScreen = true;
  setup();
  expect(screen.getByRole('tab', { name: 'Transcript' }).getAttribute('aria-selected')).toBe('true');
  expect(screen.getAllByText('Saved moments')).toHaveLength(1);
  expect(screen.getByTestId('title').textContent).toBe('Test video · Transcript');
 });
 it('carries an Overview question into Ask', () => {
  setup('?tab=overview');
  fireEvent.click(screen.getByText('Suggested question'));
  expect(screen.getByRole('tab', { name: 'Ask' }).getAttribute('aria-selected')).toBe('true');
  expect(screen.getByText('Why does this work?')).toBeTruthy();
 });
