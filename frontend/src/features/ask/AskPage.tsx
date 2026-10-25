import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageSquarePlus, Sparkles } from 'lucide-react';
import { conversationsApi, videosApi } from '../../api';
import { useWizChat } from '../../hooks/useWizChat';
import PageTitle from '../../components/PageTitle';
import WizChat from '../../components/wiz/WizChat';
import Button from '../../components/ui/Button';
import ErrorState from '../../components/ui/ErrorState';
import { formatRelative, videoTitle } from '../../lib/format';
import { shortTitle } from '../../lib/title';
import { cn } from '../../lib/utils';
import ChatLimitNotice from '../chat/ChatLimitNotice';
import { usePassageActions } from '../chat/usePassageActions';
import { citedVideoIds } from './citations';

const STARTERS = [
  'What have I watched about staying focused?',
  'Summarize what I saved this week',
  'What did I save yesterday?',
];

function History({ activeId, onPick, onNew }: { activeId: number | null; onPick: (id: number) => void; onNew: () => void }) {
  const chats = useQuery({
    queryKey: ['conversations', 'library'],
    queryFn: () => conversationsApi.list({ scope: 'library', per_page: 30 }),
  });
  return (
    <aside aria-label="Chat history" className="hidden w-64 shrink-0 lg:block">
      <Button onClick={onNew} className="mb-3 w-full justify-center"><MessageSquarePlus className="size-4" />New chat</Button>
      {chats.isPending && <p role="status" className="px-2.5 text-sm text-muted-foreground">Loading chats…</p>}
      {chats.isError && !chats.data && <ErrorState compact headingLevel={3} title="Chats did not load" message="Check your connection and try again." onRetry={() => void chats.refetch()} />}
      {chats.data?.conversations.length === 0 && <p className="px-2.5 text-sm text-muted-foreground">No chats yet.</p>}
      <ul className="space-y-0.5">
        {chats.data?.conversations.map(chat => (
          <li key={chat.id}>
            <button
              type="button"
              onClick={() => onPick(chat.id)}
              className={cn('w-full rounded-lg px-2.5 py-2 text-left hover:bg-muted', chat.id === activeId && 'bg-muted')}
            >
              <span className="line-clamp-2 text-sm">{chat.title}</span>
              <span className="text-xs text-muted-foreground">{formatRelative(chat.last_message_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default function AskPage() {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const resumeId = (() => {
    const value = Number(params.get('c'));
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  })();
  const pendingQuestion = params.get('q');
  const sentQuestion = useRef(false);

  const setConversation = useCallback((id: number | null) => {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (id === null) next.delete('c'); else next.set('c', String(id));
      return next;
    }, { replace: true });
  }, [setParams]);

  const chat = useWizChat({ scope: 'library' }, true, {
    resumeId,
    onStarted: id => {
      setConversation(id);
      void queryClient.invalidateQueries({ queryKey: ['conversations', 'library'] });
    },
  });

  // A question passed from search or the command palette is asked once.
  useEffect(() => {
    if (!pendingQuestion || sentQuestion.current || chat.isSendDisabled) return;
    sentQuestion.current = true;
    void chat.send(pendingQuestion);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.delete('q');
      return next;
    }, { replace: true });
  }, [pendingQuestion, chat, setParams]);

  const ids = citedVideoIds(chat.messages);
  const videos = useQueries({
    queries: ids.map(id => ({ queryKey: ['video', id], queryFn: () => videosApi.getVideo(id), staleTime: 300_000 })),
  });
  const titles = useMemo(() => {
    const map = new Map<string, string>();
    videos.forEach((query, index) => {
      if (query.data) map.set(ids[index], videoTitle(query.data.title, ids[index]));
    });
    return map;
    // `videos` changes identity every render; the data it holds is what matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join(','), videos.map(query => query.dataUpdatedAt).join(',')]);
  const videoLabel = useCallback((id: string) => titles.get(id), [titles]);
  const passages = usePassageActions({ signedIn: true, videoLabel });
  // A chat is named by its first question, so follow-ups and streaming keep the title.
  const firstQuestion = chat.messages.find(message => message.role === 'user')?.parts
    .map(part => (part.type === 'citation' ? '' : part.text)).join(' ');

  return (
    <div className="flex gap-6">
      <PageTitle title={firstQuestion?.trim() ? shortTitle(firstQuestion) : 'Ask your library'} />
      <History
        activeId={chat.conversationId}
        onPick={id => { setConversation(id); chat.resume(id); }}
        onNew={() => { setConversation(null); chat.newChat(); }}
      />
      <div className="min-w-0 flex-1 overflow-hidden rounded-[14px] border border-border bg-card">
        <WizChat
          chat={chat}
          isReady
          scope="library"
          suggestedQuestions={STARTERS}
          passages={passages}
          className="h-[calc(100dvh-11rem)] md:h-[calc(100dvh-8.5rem)]"
          header={<div className="flex items-center gap-2"><Sparkles className="size-4" /><h1 className="display text-lg">Ask your library</h1></div>}
          statusBanner={<ChatLimitNotice chat={chat} />}
        />
      </div>
    </div>
  );
}
