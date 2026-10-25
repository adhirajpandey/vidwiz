import { useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import {
  AssistantRuntimeProvider, useExternalStoreRuntime, useAui, useAuiState,
  ThreadPrimitive, MessagePrimitive, ComposerPrimitive, ActionBarPrimitive,
} from '@assistant-ui/react';
import type { AppendMessage, ThreadMessageLike } from '@assistant-ui/react';
import { ArrowDown, ArrowUp, Check, Copy, MessageSquarePlus, Sparkles } from 'lucide-react';
import type { WizChatController, WizMessage } from '../../hooks/useWizChat';
import ErrorState from '../ui/ErrorState';
import { Tooltip } from '../ui/Tooltip';
import WizMarkdown from './WizMarkdown';
import WizCitation, { WizPassageProvider } from './WizCitation';
import type { PassageActions } from './WizCitation';
import { cn } from '../../lib/utils';
import './wiz-chat.css';

function convertMessage(message: WizMessage): ThreadMessageLike {
  return {
    id: message.id, role: message.role, createdAt: message.createdAt,
    content: message.parts.map(part => part.type === 'block' ? { type: 'text' as const, text: part.text, citations: part.citations } : part.type === 'text' ? part
      : { type: 'data' as const, name: 'citation', data: part }),
    ...(message.role === 'assistant' ? {
      status: message.status === 'running' ? { type: 'running' as const }
        : message.status === 'error' ? { type: 'incomplete' as const, reason: 'error' as const }
        : { type: 'complete' as const, reason: 'stop' as const },
    } : {}),
    metadata: { custom: { displayError: message.error ?? null } },
  };
}

function UserMessage() {
  // The question reads as a heading for the answer below it.
  return <MessagePrimitive.Root className="border-t border-border pt-4 pb-1 mt-4 first:mt-0 first:border-t-0 first:pt-2">
    <div className="text-xl font-semibold leading-snug tracking-tight [font-stretch:90%] whitespace-pre-wrap break-words">
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>;
}

function AssistantMessage() {
  const running = useAuiState(s => s.message.status?.type === 'running');
  const hasText = useAuiState(s => s.message.content.some(part => part.type === 'text' && part.text.length > 0));
  const error = useAuiState(s => s.message.metadata.custom.displayError) as WizMessage['error'];
  const copied = useAuiState(s => s.message.isCopied);
  return <MessagePrimitive.Root className="py-3 min-w-0">
    <div className="flex items-center gap-2 mb-2 text-xs font-medium text-muted-foreground">
      <Sparkles className="size-3.5" />Wiz
      {running && <span role="status" className="font-normal motion-safe:animate-pulse">{hasText ? 'Answering…' : 'Thinking…'}</span>}
    </div>
    <MessagePrimitive.Parts components={{ Text: WizMarkdown, data: { by_name: { citation: WizCitation } } }} />
    {error && <div role="alert" className="mt-3 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-foreground">
      <p>{error.message}</p>
      {error.requestId && <p className="mt-1 text-xs text-muted-foreground">Reference: {error.requestId}</p>}
    </div>}
    {hasText && !running && <ActionBarPrimitive.Root className="mt-2">
      <ActionBarPrimitive.Copy aria-label={copied ? 'Copied answer' : 'Copy answer'} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        <span>{copied ? 'Copied' : 'Copy'}</span>
      </ActionBarPrimitive.Copy>
    </ActionBarPrimitive.Root>}
  </MessagePrimitive.Root>;
}

function StarterQuestions({ questions, intro }: { questions?: string[] | null; intro: string }) {
  const aui = useAui();
  return <div className="flex flex-col items-center justify-center text-center py-8 px-2">
    <div className="size-11 rounded-xl bg-surface flex items-center justify-center mb-3"><Sparkles className="size-5" /></div>
    <p className="text-muted-foreground text-sm max-w-sm leading-6 mb-5">{intro}</p>
    {questions && questions.length > 0 && <div className="flex flex-col gap-2 w-full">
      {questions.map(question => <button key={question} type="button"
        onClick={() => { aui.composer.setText(question); }}
        className="rounded-[10px] border border-border bg-card px-3.5 py-2.5 text-left text-sm font-medium text-foreground hover:border-foreground/40 transition-colors"
      >{question}</button>)}
    </div>}
  </div>;
}

function DraftLoader({ draft }: { draft?: { text: string; id: number } | null }) {
  const aui = useAui();
  const applied = useRef<object | null>(null);
  useEffect(() => {
    if (draft && applied.current !== draft) {
      aui.composer.setText(draft.text);
      applied.current = draft;
    }
  }, [aui, draft]);
  return null;
}

interface Props {
  draft?: { text: string; id: number } | null;
  chat: WizChatController;
  isReady: boolean;
  suggestedQuestions?: string[] | null;
  passages: PassageActions;
  statusBanner?: ReactNode;
  scope?: 'video' | 'library';
  header?: ReactNode;
  className?: string;
}

const COPY = {
  video: {
    intro: 'Ask about this video. Citations jump straight to the moment it was said.',
    placeholder: 'Ask about this video…',
    footer: "Answers come from this video's transcript",
  },
  library: {
    intro: 'Ask about anything you have saved. Answers cite the videos and moments they come from.',
    placeholder: 'Ask your library…',
    footer: 'Answers come from your saved videos and moments',
  },
};

export default function WizChat({ chat, isReady, suggestedQuestions, passages, statusBanner, scope = 'video', header, className, draft }: Props) {
  const copy = COPY[scope];
  const { send } = chat;
  const onNew = useCallback(async (message: AppendMessage) => {
    const text = message.content.filter(part => part.type === 'text').map(part => part.text).join('\n');
    await send(text);
  }, [send]);
  const runtime = useExternalStoreRuntime({
    messages: chat.messages, convertMessage, onNew,
    isRunning: chat.isRunning, isSendDisabled: chat.isSendDisabled,
  });
  return <AssistantRuntimeProvider runtime={runtime}>
    <DraftLoader draft={draft} />
    <WizPassageProvider value={passages}>
      <ThreadPrimitive.Root className={cn('flex min-h-0 flex-col overflow-hidden', className)}>
        <div className="flex min-h-11 items-center justify-between gap-2 px-3 py-1.5 border-b border-border">
          {header ?? <div className="flex items-center gap-2"><Sparkles className="size-4" /><h2 className="text-sm font-bold">Ask</h2></div>}
          {chat.messages.length > 0 && <button type="button" onClick={chat.newChat} className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"><MessageSquarePlus className="size-4 shrink-0" />New chat</button>}
        </div>
        {statusBanner}
        <div className="relative flex flex-1 min-h-0 flex-col">
          <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto px-4 md:px-5 py-2" autoScroll>
            {chat.conversationError && <ErrorState compact title="Unable to start chat" message={chat.conversationError.message} referenceId={chat.conversationError.requestId} onRetry={() => void chat.retryConversation()} />}
            {chat.isLoadingHistory && <p role="status" className="py-8 text-center text-sm text-muted-foreground">Loading conversation…</p>}
            {isReady && !chat.conversationError && !chat.isLoadingHistory && <ThreadPrimitive.Empty><StarterQuestions questions={suggestedQuestions} intro={copy.intro} /></ThreadPrimitive.Empty>}
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
            <div className="sticky bottom-2 flex justify-center pointer-events-none">
              <Tooltip label="Latest message"><ThreadPrimitive.ScrollToBottom aria-label="Scroll to latest message" className="pointer-events-auto rounded-full border border-border bg-card p-2 shadow-md disabled:hidden"><ArrowDown className="size-4" /></ThreadPrimitive.ScrollToBottom></Tooltip>
            </div>
          </ThreadPrimitive.Viewport>
        </div>
        <div className="p-3 md:p-4 border-t border-border">
          <ComposerPrimitive.Root className="flex items-end gap-2 rounded-[12px] border border-input bg-card p-2 focus-within:border-foreground/60 has-[textarea:focus-visible]:outline-2 has-[textarea:focus-visible]:outline-offset-2 has-[textarea:focus-visible]:outline-accent">
            <ComposerPrimitive.Input aria-label="Message Wiz" placeholder={isReady ? copy.placeholder : 'Waiting for the transcript…'} submitMode="enter" rows={1} className="flex-1 min-w-0 max-h-36 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground" />
            <Tooltip label="Send"><ComposerPrimitive.Send aria-label="Send message" className="shrink-0 rounded-[9px] bg-accent text-accent-foreground p-2.5 hover:opacity-90 disabled:opacity-40"><ArrowUp className="size-4" /></ComposerPrimitive.Send></Tooltip>
          </ComposerPrimitive.Root>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">{copy.footer}</p>
        </div>
      </ThreadPrimitive.Root>
    </WizPassageProvider>
  </AssistantRuntimeProvider>;
}
