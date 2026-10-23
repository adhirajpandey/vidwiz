// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { WizMessage } from '../../hooks/useWizChat';
import AskPage from './AskPage';

let messages: WizMessage[] = [];
vi.mock('../../api', () => ({
  conversationsApi: { list: () => Promise.resolve({ conversations: [] }) },
  videosApi: { getVideo: () => Promise.resolve(null) },
}));
vi.mock('../../hooks/useWizChat', () => ({
  useWizChat: () => ({ messages, conversationId: null, isSendDisabled: true }),
}));
vi.mock('../chat/usePassageActions', () => ({ usePassageActions: () => ({}) }));
vi.mock('../../components/wiz/WizChat', () => ({ default: () => null }));
vi.mock('../../components/PageTitle', () => ({
  default: ({ title }: { title: string }) => <output data-testid="title">{title}</output>,
}));
afterEach(() => { cleanup(); messages = []; });

const message = (role: WizMessage['role'], text: string): WizMessage => ({
  id: text, role, parts: [{ type: 'text', text }], createdAt: new Date(),
});

function setup() {
  render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={['/ask']}><AskPage /></MemoryRouter>
  </QueryClientProvider>);
  return screen.getByTestId('title').textContent;
}

describe('library chat tab title', () => {
  it('names a new chat Ask your library', () => {
    expect(setup()).toBe('Ask your library');
  });

  it('keeps the first question, shortened, through follow-ups and answers', () => {
    const first = 'What have I watched about staying focused when working from home on long afternoons?';
    messages = [
      message('user', first),
      message('assistant', 'Several videos cover this.'),
      message('user', 'And on weekends?'),
    ];
    expect(setup()).toBe('What have I watched about staying focused when working from…');
  });

  it('uses New chat and Chat history', () => {
    setup();
    expect(screen.getByRole('button', { name: 'New chat' })).toBeTruthy();
    expect(screen.getByRole('complementary', { name: 'Chat history' })).toBeTruthy();
  });
});
