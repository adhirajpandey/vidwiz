import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch, conversationsApi, normalizeApiError, normalizeFetchError, readSseEvents } from '../api';
import type { NormalizedApiError } from '../api/errors';
import { parseWizEvent, type MessagePart, type WizStreamEvent } from '../api/messageParts';
import type { MessageRead } from '../api/types';
import { getToken } from '../lib/authUtils';

export interface WizMessage {
  id: string;
  role: 'user' | 'assistant';
  parts: MessagePart[];
  serverMessageId?: number;
  createdAt: Date;
  status?: 'running' | 'complete' | 'error';
  error?: { message: string; requestId?: string };
}

type Limit = { kind: 'guest' | 'user'; resetSeconds: number | null };

/** What the chat is about: one video, or the user's whole library. */
export type ChatTarget = { scope: 'video'; videoId: string } | { scope: 'library' };

function targetKey(target: ChatTarget | null): string | null {
  if (!target) return null;
  return target.scope === 'video' ? `video:${target.videoId}` : 'library';
}

interface Session {
  generation: number;
  key: string;
  target: ChatTarget;
  conversationId: number | null;
  creation?: Promise<number | null>;
  request?: AbortController;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function fromServer(message: MessageRead): WizMessage {
  return {
    id: `server-${message.id}`,
    role: message.role,
    parts: message.parts,
    serverMessageId: message.role === 'assistant' ? message.id : undefined,
    createdAt: new Date(message.created_at),
    status: 'complete',
  };
}

/**
 * VidWiz chat transport and state. UI libraries adapt these domain values at
 * their boundary. Pass `resumeId` to continue a saved conversation; `onStarted`
 * reports the id of a conversation once it exists.
 */
export function useWizChat(
  target: ChatTarget | null,
  isReady: boolean,
  { resumeId = null, onStarted }: { resumeId?: number | null; onStarted?: (id: number) => void } = {},
) {
  const key = targetKey(target);
  const targetRef = useRef(target);
  targetRef.current = target;
  const onStartedRef = useRef(onStarted);
  onStartedRef.current = onStarted;
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [messages, setMessages] = useState<WizMessage[]>([]);
  const [generation, setGeneration] = useState(0);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [conversationError, setConversationError] = useState<NormalizedApiError | null>(null);
  const [limit, setLimit] = useState<Limit | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const active = useRef<Session | null>(null);
  const sequence = useRef(0);

  const createConversation = useCallback((session: Session): Promise<number | null> => {
    if (active.current !== session) return Promise.resolve(null);
    if (session.creation) return session.creation;
    if (session.conversationId !== null) return Promise.resolve(session.conversationId);
    setIsCreatingConversation(true);
    setConversationError(null);
    if (session.target.scope === 'video' && !getToken() && !sessionStorage.getItem('guestSessionId')) {
      sessionStorage.setItem('guestSessionId', crypto.randomUUID());
    }
    session.creation = (async () => {
      try {
        const result = await conversationsApi.createConversation(
          session.target.scope === 'video'
            ? { scope: 'video', video_id: session.target.videoId }
            : { scope: 'library' },
        );
        if (active.current !== session) return null;
        session.conversationId = result.id;
        setConversationId(result.id);
        onStartedRef.current?.(result.id);
        return result.id;
      } catch (error) {
        if (active.current !== session) return null;
        const normalized = normalizeApiError(error, 'Unable to start a conversation. Please try again.');
        if (!normalized.handled) setConversationError(normalized);
        return null;
      } finally {
        if (active.current === session) {
          session.creation = undefined;
          setIsCreatingConversation(false);
        }
      }
    })();
    return session.creation;
  }, []);

  const startSession = useCallback((resume: number | null = null) => {
    active.current?.request?.abort();
    const current = targetRef.current;
    const session: Session | null = key && current
      ? { generation: ++sequence.current, key, target: current, conversationId: resume }
      : null;
    active.current = session;
    setGeneration(sequence.current);
    setConversationId(resume);
    setMessages([]);
    setIsRunning(false);
    setIsCreatingConversation(Boolean(session) && resume === null);
    setIsLoadingHistory(Boolean(session) && resume !== null);
    setConversationError(null);
    setLimit(null);
    setIsProcessing(false);
    // Defer requests so React StrictMode's discarded effect creates no conversation.
    queueMicrotask(() => {
      if (!session || active.current !== session) return;
      if (resume === null) {
        void createConversation(session);
        return;
      }
      void conversationsApi.listMessages(resume).then(history => {
        if (active.current === session) setMessages(history.map(fromServer));
      }).catch(error => {
        if (active.current !== session) return;
        const normalized = normalizeApiError(error, 'This conversation could not be loaded.');
        if (!normalized.handled) setConversationError(normalized);
      }).finally(() => {
        if (active.current === session) setIsLoadingHistory(false);
      });
    });
  }, [key, createConversation]);

  useEffect(() => {
    startSession(resumeId);
    return () => {
      active.current?.request?.abort();
      active.current = null;
    };
    // Resuming is decided when the chat opens; later id changes come from this hook.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startSession]);

  const retryConversation = useCallback(async () => {
    const session = active.current;
    if (session) await createConversation(session);
  }, [createConversation]);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    const session = active.current;
    if (!message || !session || session.key !== key || !isReady ||
        conversationError || session.creation || session.request || session.conversationId === null) return;
    const id = session.conversationId;
    const controller = new AbortController();
    // Synchronous guard, independent of the next React render.
    session.request = controller;
    const isCurrent = () => active.current === session && session.conversationId === id &&
      session.request === controller && !controller.signal.aborted;
    setIsRunning(true);
    const assistantId = crypto.randomUUID();
    setMessages(previous => [...previous,
      { id: crypto.randomUUID(), role: 'user', parts: [{ type: 'text', text: message }], createdAt: new Date() },
      { id: assistantId, role: 'assistant', parts: [], createdAt: new Date(), status: 'running' },
    ]);
    const update = (patch: Partial<WizMessage>) => {
      if (isCurrent()) setMessages(previous => previous.map(item =>
        item.id === assistantId ? { ...item, ...patch } : item));
    };
    const removePlaceholder = () => {
      if (isCurrent()) setMessages(previous => previous.filter(item => item.id !== assistantId));
    };
    const parts: MessagePart[] = [];
    let requestId: string | undefined;
    let displayError: WizMessage['error'];
    try {
      const response = await apiFetch(conversationsApi.getSendMessageUrl(id), {
        method: 'POST', body: JSON.stringify({ message, parts_version: 2 }), signal: controller.signal,
      });
      if (!isCurrent()) return;
      requestId = response.headers.get('X-Request-ID') ?? undefined;
      if (response.status === 401) {
        removePlaceholder();
        return;
      }
      if (response.status === 429) {
        const error = await normalizeFetchError(response, 'You have reached the current chat limit.');
        if (!isCurrent()) return;
        removePlaceholder();
        setLimit({ kind: getToken() ? 'user' : 'guest', resetSeconds: error.retryAfterSeconds ?? null });
        return;
      }
      if (response.status === 202) {
        let processingMessage = 'Transcript processing';
        try {
          const data: unknown = await response.json();
          if (isRecord(data) && typeof data.message === 'string') processingMessage = data.message;
        } catch { /* Keep the existing processing fallback. */ }
        if (!isCurrent()) return;
        update({ parts: [{ type: 'text', text: processingMessage }], status: 'complete' });
        setIsProcessing(true);
        return;
      }
      if (!response.ok) {
        const error = await normalizeFetchError(response, 'Chat is temporarily unavailable. Please try again.');
        displayError = { message: error.message, requestId: error.requestId ?? requestId };
        throw new Error('Chat request failed');
      }
      if (!response.body) {
        displayError = { message: 'The chat response could not be read. Please try again.', requestId };
        throw new Error('Missing response body');
      }
      let done = false;
      for await (const event of readSseEvents(response.body)) {
        if (!isCurrent()) return;
        let data: WizStreamEvent;
        try { data = parseWizEvent(JSON.parse(event.data)); } catch {
          displayError = { message: 'The server returned an invalid chat response.', requestId };
          throw new Error('Invalid stream event');
        }
        if (data.type === 'done') {
          done = true;
          update({ serverMessageId: data.message_id });
          break;
        }
        if (data.type === 'error') {
          displayError = { message: data.message, requestId };
          throw new Error('Stream error');
        }
        parts.push(data);
        update({ parts: [...parts] });
      }
      const hasText = parts.some(part => part.type !== 'citation' && part.text.trim());
      if (!hasText || !done) {
        update({ status: 'error', error: {
          message: parts.length ? 'The response was interrupted. Please try again.' : 'No response received. Please try again.',
          requestId,
        } });
      } else update({ status: 'complete' });
    } catch {
      update({ status: 'error', error: displayError ?? {
        message: 'The chat connection failed. Please try again.', requestId,
      } });
    } finally {
      if (isCurrent()) {
        session.request = undefined;
        setIsRunning(false);
      }
      // Release this Fetch stream only; this does not cancel server-side generation.
      controller.abort();
    }
  }, [key, isReady, conversationError]);

  return {
    messages, generation, conversationId, isRunning, isCreatingConversation, conversationError,
    isLoadingHistory,
    isSendDisabled: isRunning || isCreatingConversation || isLoadingHistory || !isReady ||
      Boolean(conversationError) || conversationId === null,
    send, newChat: () => startSession(null), resume: (id: number) => startSession(id),
    retryConversation, limit, isProcessing,
    dismissLimit: () => setLimit(null), dismissProcessing: () => setIsProcessing(false),
  };
}

export type WizChatController = ReturnType<typeof useWizChat>;
