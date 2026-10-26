// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { WizMessage } from '../../hooks/useWizChat';
import AskPage from './AskPage';
import { conversationsApi } from '../../api';

let messages: WizMessage[] = [];
let conversations: { id: number; title: string; last_message_at: string }[] = [];
let conversationId: number | null = null;
const resume = vi.fn();
vi.mock('../../api', () => ({
  conversationsApi: { list: vi.fn(() => Promise.resolve({ conversations })) },
  videosApi: { getVideo: () => Promise.resolve(null) },
}));
vi.mock('../../hooks/useWizChat', () => ({
  useWizChat: () => ({ messages, conversationId, isSendDisabled: true, resume }),
}));
vi.mock('../chat/usePassageActions', () => ({ usePassageActions: () => ({}) }));
vi.mock('../../components/wiz/WizChat', () => ({ default: ({ header }: { header: React.ReactNode }) => <div data-testid="chat-header">{header}</div> }));
vi.mock('../../components/PageTitle', () => ({
  default: ({ title }: { title: string }) => <output data-testid="title">{title}</output>,
}));
afterEach(() => { cleanup(); messages = []; conversations = []; conversationId = null; resume.mockClear(); vi.mocked(conversationsApi.list).mockReset().mockImplementation(() => Promise.resolve({ conversations }) as ReturnType<typeof conversationsApi.list>); });

const message = (role: WizMessage['role'], text: string): WizMessage => ({
  id: text, role, parts: [{ type: 'text', text }], createdAt: new Date(),
});

function setup() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
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

describe('library chat history below desktop width', () => {
  it('offers the sidebar chats as a menu, marks the open chat, and keeps the heading', async () => {
    const user = userEvent.setup();
    conversations = [
      { id: 1, title: 'Staying focused', last_message_at: new Date().toISOString() },
      { id: 2, title: 'Learning faster', last_message_at: new Date().toISOString() },
    ];
    conversationId = 2;
    setup();
    const header = screen.getByTestId('chat-header');
    expect(within(header).getByRole('heading', { level: 1, name: 'Ask your library' })).toBeTruthy();
    const sidebar = screen.getByRole('complementary', { name: 'Chat history' });
    expect((await within(sidebar).findByRole('button', { name: /Learning faster/ })).getAttribute('aria-current')).toBe('true');

    await user.click(within(header).getByRole('button', { name: 'Chat history' }));
    const items = screen.getAllByRole('menuitem');
    expect(items.map(item => item.getAttribute('aria-current'))).toEqual([null, 'true']);
    await user.click(items[0]);
    expect(resume).toHaveBeenCalledWith(1);
  });
});

it('retries a failed history request from the compact header', async () => {
  const user = userEvent.setup();
  vi.mocked(conversationsApi.list).mockRejectedValueOnce(new Error('Offline'));
  conversations = [{ id: 1, title: 'Recovered chat', last_message_at: new Date().toISOString() }];
  setup();
  const header = screen.getByTestId('chat-header');
  await user.click(await within(header).findByRole('button', { name: 'Retry history' }));
  await user.click(await within(header).findByRole('button', { name: 'Chat history' }));
  expect(await screen.findByRole('menuitem', { name: /Recovered chat/ })).toBeTruthy();
  expect(conversationsApi.list).toHaveBeenCalledTimes(2);
});
