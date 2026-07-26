import { useCallback, useState, useRef, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Send, Sparkles, RotateCcw } from 'lucide-react';
import { FaExternalLinkAlt } from 'react-icons/fa';
import { extractVideoId } from '../lib/videoUtils';
import GuestLimitModal from '../components/GuestLimitModal';
import RegisteredLimitModal from '../components/RegisteredLimitModal';
import Seo from '../components/Seo';
import ErrorState from '../components/ui/ErrorState';
import { getToken } from '../lib/authUtils';
import {
  apiFetch,
  conversationsApi,
  normalizeApiError,
  normalizeFetchError,
  readSseEvents,
  videosApi,
} from '../api';
import type { NormalizedApiError } from '../api/errors';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: { start_seconds: number; end_seconds?: number; label: string }[];
  createdAt: Date;
}

interface VideoData {
  video_id: string;
  title: string | null;
  transcript_available: boolean;
  metadata: {
    title?: string;
    channel?: string;
    channel_url?: string;
    uploader?: string;
    uploader_url?: string;
    duration_string?: string;
    thumbnail?: string;
    view_count?: number;
    like_count?: number;
    upload_date?: string;
  } | null;
  summary: string | null;
  suggested_questions: string[] | null;
}

interface WizStreamPayload {
  error?: string;
  content?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isWizStreamPayload(value: unknown): value is WizStreamPayload {
  if (!isRecord(value)) {
    return false;
  }

  return (
    (value.error === undefined || typeof value.error === 'string') &&
    (value.content === undefined || typeof value.content === 'string')
  );
}

function isVideoData(value: unknown): value is VideoData {
  if (!isRecord(value)) return false;
  const suggestedQuestions = value.suggested_questions;
  return (
    typeof value.video_id === 'string' &&
    (value.title === null || typeof value.title === 'string') &&
    typeof value.transcript_available === 'boolean' &&
    (value.metadata === null || isRecord(value.metadata)) &&
    (value.summary === null || typeof value.summary === 'string') &&
    (
      suggestedQuestions === null ||
      suggestedQuestions === undefined ||
      (
        Array.isArray(suggestedQuestions) &&
        suggestedQuestions.every((question) => typeof question === 'string')
      )
    )
  );
}

function parseJsonPayload(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    throw new Error('The server returned an invalid stream response.');
  }
}

class ChatDisplayError extends Error {
  requestId?: string;

  constructor(message: string, requestId?: string) {
    super(message);
    this.name = 'ChatDisplayError';
    this.requestId = requestId;
  }
}

// ConversationResponse removed

/**
 * Parses bold markdown (**text**) and renders as bold
 */
function parseBoldText(content: string, keyPrefix: string = ''): React.ReactNode {
  const boldRegex = /\*\*([\s\S]+?)\*\*/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = boldRegex.exec(content)) !== null) {
    if (match!.index > lastIndex) {
      parts.push(content.slice(lastIndex, match!.index));
    }
    parts.push(
      <strong
        key={`${keyPrefix}-bold-${match!.index}`}
        className="font-bold text-foreground"
      >
        {match![1]}
      </strong>
    );
    lastIndex = match!.index + match![0].length;
  }

  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.length > 0 ? parts : content;
}

/**
 * Parses timestamp citations from message content and makes them clickable
 * Supports formats: [mm:ss], [hh:mm:ss]
 * Also parses bold markdown (**text**)
 */
function parseTimestampCitations(content: string, onTimestampClick: (seconds: number) => void): React.ReactNode {
  // Matches [ ... ] blocks containing digits, colons, commas, spaces
  const citationBlockRegex = /\[([\d:, ]+)\]/g;
  
  // Regex to validate individual timestamps inside the block
  // Matches mm:ss or hh:mm:ss
  const timestampPattern = /^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$/;

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  const renderTimestampButton = (label: string, secondsValue: number, key: string) => (
    <button
      key={key}
      onClick={() => onTimestampClick(secondsValue)}
      className="inline-flex items-center align-middle px-1.5 py-0.5 mx-0.5 rounded-md bg-violet-500/10 text-violet-600 dark:text-violet-300 hover:bg-violet-500/20 transition-all text-sm font-mono border border-violet-500/20 cursor-pointer"
    >
      {label}
    </button>
  );

  const toSeconds = (hasHours: boolean, a: string, b: string, c?: string) => {
    const hours = hasHours ? parseInt(a) : 0;
    const minutes = hasHours ? parseInt(b) : parseInt(a);
    const seconds = hasHours ? parseInt(c || '0') : parseInt(b);
    return hours * 3600 + minutes * 60 + seconds;
  };

  const formatLabel = (hasHours: boolean, a: string, b: string, c?: string) => {
    if (hasHours) {
      return `${parseInt(a)}:${b}:${c || '00'}`;
    }
    return `${parseInt(a)}:${b}`;
  };

  while ((match = citationBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      // Parse bold in text between citation blocks
      parts.push(parseBoldText(content.slice(lastIndex, match.index), `pre-${match.index}`));
    }

    const innerContent = match[1];
    const timestampParts = innerContent.split(',');
    
    const blockElements: React.ReactNode[] = [];
    
    timestampParts.forEach((part, idx) => {
      const trimmed = part.trim();
      const tsMatch = timestampPattern.exec(trimmed);

      if (idx > 0) {
        blockElements.push(<span key={`comma-${match!.index}-${idx}`}>, </span>);
      }

      if (tsMatch) {
        const hasHours = tsMatch[3] !== undefined;
        const secondsValue = toSeconds(hasHours, tsMatch[1], tsMatch[2], tsMatch[3]);
        const label = formatLabel(hasHours, tsMatch[1], tsMatch[2], tsMatch[3]);
        blockElements.push(
          renderTimestampButton(label, secondsValue, `btn-${match!.index}-${idx}`)
        );
      } else {
        // If part doesn't look like a timestamp, just render text
        blockElements.push(<span key={`text-${match!.index}-${idx}`}>{trimmed}</span>);
      }
    });

    // Push the whole constructed block
    parts.push(<span key={`block-${match!.index}`}>{blockElements}</span>);

    lastIndex = match!.index + match![0].length;
  }

  if (lastIndex < content.length) {
    // Parse bold in remaining text
    parts.push(parseBoldText(content.slice(lastIndex), `post-${lastIndex}`));
  }

  return parts.length > 0 ? parts : parseBoldText(content, 'no-ts');
}

function WizWorkspacePage() {
  const params = useParams();
  const location = useLocation();
  
  // Reconstruct full input by adding query params back to the path
  const rawInput = (params['*'] || '') + location.search;
  const videoId = extractVideoId(rawInput);
  
  const navigate = useNavigate();

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [videoData, setVideoData] = useState<VideoData | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [isPolling, setIsPolling] = useState(true);
  const [showRefreshModal, setShowRefreshModal] = useState(false);
  const [showGuestLimit, setShowGuestLimit] = useState(false);
  const [showRegisteredLimit, setShowRegisteredLimit] = useState(false);
  const [resetSeconds, setResetSeconds] = useState<number | null>(null);
  const [statusError, setStatusError] = useState<NormalizedApiError | null>(null);
  const [conversationError, setConversationError] = useState<NormalizedApiError | null>(null);
  const [statusAttempt, setStatusAttempt] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLIFrameElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollingStartTime = useRef<number>(Date.now());
  const videoDataRef = useRef<VideoData | null>(null);
  const initializedConversationVideoIdRef = useRef<string | null>(null);

  // Handle URL normalization and redirects
  // Handle URL normalization and redirects
  useEffect(() => {
    if (!rawInput) {
      navigate('/wiz', { replace: true });
      return;
    }
    
    // If extraction failed or returned null
    if (!videoId) {
      // Invalid ID or URL
      navigate('/wiz', { replace: true });
      return;
    }

    // If the raw input is different from the clean ID (e.g. it was a full URL),
    // redirect to the clean ID version
    if (videoId !== rawInput) {
      navigate(`/wiz/${videoId}`, { replace: true });
    }
  }, [rawInput, videoId, navigate]);

  // Reset state when videoId changes
  useEffect(() => {
    setMessages([]);
    setVideoData(null);
    setIsPolling(true);
    setConversationId(null);
    setShowRefreshModal(false);
    setStatusError(null);
    setConversationError(null);
    // Reset refs
    pollingStartTime.current = Date.now();
  }, [videoId]);

  // Computed status
  const transcriptStatus = videoData?.transcript_available ? 'ready' : 'loading';

  useEffect(() => {
    videoDataRef.current = videoData;
  }, [videoData]);

  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [messages]);

  // Stream video status via SSE, fallback to polling if stream fails
  useEffect(() => {
    if (!videoId) return;

    const STREAM_TIMEOUT_MS = 60000;
    const POLL_INTERVAL_MS = 5000;
    let isCancelled = false;
    let abortController: AbortController | null = null;
    let timeoutId: number | undefined;
    let intervalId: number | undefined;
    let hasTimedOut = false;
    let pollingStarted = false;
    let hasSuccessfulStatusCheck = false;
    let lastStatusError: NormalizedApiError | null = null;
    let consecutivePollFailures = 0;

    const handleTimeout = () => {
      hasTimedOut = true;
      setIsPolling(false);
      if (!videoDataRef.current?.transcript_available) {
        if (
          lastStatusError &&
          (!hasSuccessfulStatusCheck || consecutivePollFailures > 0)
        ) {
          setStatusError(lastStatusError);
        } else {
          setShowRefreshModal(true);
        }
      }
      if (abortController) {
        abortController.abort();
      }
      if (intervalId) {
        clearInterval(intervalId);
      }
    };

    const pollFallback = async () => {
      try {
        const data = await videosApi.getVideo(videoId);
        hasSuccessfulStatusCheck = true;
        lastStatusError = null;
        consecutivePollFailures = 0;
        setStatusError(null);
        setVideoData(data);
        if (data.transcript_available && data.metadata && data.summary) {
          setIsPolling(false);
          if (intervalId) {
            clearInterval(intervalId);
          }
          if (timeoutId) {
            clearTimeout(timeoutId);
          }
        }
      } catch (error) {
        lastStatusError = normalizeApiError(
          error,
          'Unable to check the video status. Please try again.'
        );
        consecutivePollFailures += 1;
        console.error('Failed to fetch video status:', error);
      }
    };

    const startPolling = () => {
      if (pollingStarted || hasTimedOut) return;
      pollingStarted = true;
      void pollFallback();
      intervalId = window.setInterval(() => {
        if (Date.now() - pollingStartTime.current >= STREAM_TIMEOUT_MS) {
          handleTimeout();
          return;
        }
        void pollFallback();
      }, POLL_INTERVAL_MS);
    };

    const startStream = async () => {
      setIsPolling(true);
      setStatusError(null);
      timeoutId = window.setTimeout(handleTimeout, STREAM_TIMEOUT_MS);

      // Ensure guest session id exists for unauthenticated users
      const token = getToken();
      if (!token && !sessionStorage.getItem('guestSessionId')) {
        sessionStorage.setItem('guestSessionId', crypto.randomUUID());
      }

      abortController = new AbortController();

      try {
        const response = await apiFetch(videosApi.getStreamUrl(videoId), {
          method: 'GET',
          signal: abortController.signal,
        });

        if (response.status === 401) {
          if (timeoutId) clearTimeout(timeoutId);
          setIsPolling(false);
          return;
        }

        if (!response.ok) {
          lastStatusError = await normalizeFetchError(
            response,
            'Unable to check the video status. Please try again.'
          );
          throw new Error('Video status stream unavailable');
        }
        if (!response.body) {
          lastStatusError = {
            message: 'Unable to read the video status. Please try again.',
            kind: 'stream',
            retryable: true,
          };
          throw new Error('Video status stream unavailable');
        }

        for await (const event of readSseEvents(response.body)) {
          if (isCancelled) return;
          const payload = parseJsonPayload(event.data);
          if (
            !isRecord(payload) ||
            !isVideoData(payload.video)
          ) {
            throw new Error('The server returned an invalid video status.');
          }
          hasSuccessfulStatusCheck = true;
          setVideoData(payload.video);
          if (event.event === 'done') {
            setIsPolling(false);
            if (timeoutId) clearTimeout(timeoutId);
            return;
          }
        }
        if (!isCancelled && !hasTimedOut) {
          lastStatusError = {
            message: 'The video status connection ended unexpectedly.',
            kind: 'stream',
            retryable: true,
          };
          startPolling();
        }
      } catch (error) {
        if (!isCancelled && !hasTimedOut) {
          if (!lastStatusError && !(error instanceof DOMException && error.name === 'AbortError')) {
            lastStatusError = {
              message: 'Unable to check the video status. Please try again.',
              kind: 'stream',
              retryable: true,
            };
          }
          console.error('Video status stream error:', error);
          startPolling();
        }
      }
    };

    startStream();

    return () => {
      isCancelled = true;
      if (abortController) {
        abortController.abort();
      }
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [statusAttempt, videoId]);

  const seekToTimestamp = (seconds: number) => {
    // Scroll video into view (especially for mobile)
    playerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (playerRef.current?.contentWindow) {
      playerRef.current.contentWindow.postMessage(
        JSON.stringify({
          event: 'command',
          func: 'seekTo',
          args: [seconds, true],
        }),
        '*'
      );
    }
  };

  // Ensure guest session ID exists
  useEffect(() => {
    const token = getToken();
    let guestSessionId = sessionStorage.getItem('guestSessionId');
    if (!token && !guestSessionId) {
      guestSessionId = crypto.randomUUID();
      sessionStorage.setItem('guestSessionId', guestSessionId);
    }
  }, []);

  const createNewConversation = useCallback(async () => {
    if (!videoId || isCreatingConversation) return null;
    setIsCreatingConversation(true);
    setConversationError(null);
    try {
      const data = await conversationsApi.createConversation({ video_id: videoId });
      setConversationId(data.id);
      return data.id;
    } catch (error) {
      const normalized = normalizeApiError(
        error,
        'Unable to start a conversation. Please try again.'
      );
      console.error('Failed to create conversation:', error);
      if (normalized.handled) return null;
      setConversationError(normalized);
      return null;
    } finally {
      setIsCreatingConversation(false);
    }
  }, [isCreatingConversation, videoId]);

  useEffect(() => {
    if (!videoId) {
      initializedConversationVideoIdRef.current = null;
      return;
    }
    if (initializedConversationVideoIdRef.current === videoId) {
      return;
    }
    initializedConversationVideoIdRef.current = videoId;
    void createNewConversation();
  }, [createNewConversation, videoId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (
      !trimmed ||
      isLoading ||
      transcriptStatus !== 'ready' ||
      conversationError
    ) return;

    setIsLoading(true);
    let activeConversationId = conversationId;
    if (!activeConversationId) {
      activeConversationId = await createNewConversation();
    }
    if (!activeConversationId) {
      setIsLoading(false);
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmed,
      createdAt: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    // Create assistant message placeholder for streaming
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      createdAt: new Date(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await apiFetch(
        conversationsApi.getSendMessageUrl(activeConversationId),
        {
        method: 'POST',
        body: JSON.stringify({
          message: trimmed
        }),
        }
      );
      const requestId = response.headers.get('X-Request-ID') ?? undefined;

      if (response.status === 401) {
        setMessages((prev) =>
          prev.filter((message) => message.id !== assistantMessageId)
        );
        return;
      }

      if (response.status === 429) {
        const normalized = await normalizeFetchError(
          response,
          'You have reached the current chat limit.'
        );
        setMessages((prev) =>
          prev.filter((message) => message.id !== assistantMessageId)
        );
        if (getToken()) {
          setResetSeconds(normalized.retryAfterSeconds ?? null);
          setShowRegisteredLimit(true);
        } else {
          setShowGuestLimit(true);
        }
        return;
      }

      if (response.status === 202) {
        let processingMessage = 'Transcript processing';
        try {
          const data: unknown = await response.json();
          if (isRecord(data) && typeof data.message === 'string') {
            processingMessage = data.message;
          }
        } catch {
          // Fallback to default message
        }
        setShowRefreshModal(true);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: processingMessage }
              : msg
          )
        );
        setIsLoading(false);
        return;
      }

      if (!response.ok) {
        const normalized = await normalizeFetchError(
          response,
          'Chat is temporarily unavailable. Please try again.'
        );
        throw new ChatDisplayError(normalized.message, normalized.requestId);
      }

      if (!response.body) {
        throw new ChatDisplayError(
          'The chat response could not be read. Please try again.',
          requestId
        );
      }

      let fullContent = '';
      let streamDone = false;
      for await (const event of readSseEvents(response.body)) {
        if (event.data === '[DONE]') {
          streamDone = true;
          break;
        }
        const parsed = parseJsonPayload(event.data);
        if (!isWizStreamPayload(parsed)) {
          throw new ChatDisplayError(
            'The server returned an invalid chat response.',
            requestId
          );
        }
        if (parsed.error) {
          throw new ChatDisplayError(parsed.error, requestId);
        }
        if (parsed.content) {
          fullContent += parsed.content;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: fullContent }
                : msg
            )
          );
          setIsLoading(false);
        }
      }

      if (!fullContent) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: 'No response received. Please try again.' }
              : msg
          )
        );
      } else if (!streamDone) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: `${fullContent}\n\nError: The response was interrupted. Please try again.`,
                }
              : msg
          )
        );
      }
    } catch (error) {
      console.error('Chat error:', error);
      const message =
        error instanceof ChatDisplayError
          ? error.message
          : 'The chat connection failed. Please try again.';
      const referenceId =
        error instanceof ChatDisplayError ? error.requestId : undefined;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: `Error: ${message}${referenceId ? `\n\nReference: ${referenceId}` : ''}`,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId(null);
    setConversationError(null);
    void createNewConversation();
    inputRef.current?.focus();
  };

  const retryVideoStatus = () => {
    setShowRefreshModal(false);
    setStatusError(null);
    pollingStartTime.current = Date.now();
    setStatusAttempt((attempt) => attempt + 1);
  };

  const seoVideoTitleRaw = videoData?.title || videoData?.metadata?.title || 'this YouTube video';
  const seoVideoTitle =
    seoVideoTitleRaw.length > 32 ? `${seoVideoTitleRaw.slice(0, 32).trim()}..` : seoVideoTitleRaw;
  const seoTitle = `Wiz: Chat with ${seoVideoTitle} | VidWiz`;
  const seoDescription = `Ask, don’t scrub. Chat with this YouTube video in Wiz using transcript-grounded answers and clickable timestamp citations.`;

  return (
    <>
      <Seo
        key={seoTitle}
        title={seoTitle}
        description={seoDescription}
        path={videoId ? `/wiz/${videoId}` : '/wiz'}
        ogImage="https://vidwiz.online/og-wiz.png"
        noIndex
      />
      <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-5">
      {/* Refresh Modal */}
      {showRefreshModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-card rounded-2xl p-6 max-w-md w-full mx-4 border border-border shadow-2xl">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-orange-500/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">Transcript still processing</h3>
              <p className="text-sm text-foreground/60 mb-6">
                Wiz needs a little more time to prepare this video. Check again
                without leaving the conversation.
              </p>
              <button
                onClick={retryVideoStatus}
                className="w-full px-4 py-3 bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white font-semibold rounded-xl transition-all"
              >
                Check again
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Guest Limit Modal */}
      <GuestLimitModal 
        isOpen={showGuestLimit} 
        onClose={() => setShowGuestLimit(false)} 
      />

      {/* Registered User Limit Modal */}
      <RegisteredLimitModal
        isOpen={showRegisteredLimit}
        onClose={() => setShowRegisteredLimit(false)}
        resetInSeconds={resetSeconds}
      />

      {/* Main Content - Split View: Chat Left, Video Right */}
      <div className="flex flex-col-reverse lg:flex-row lg:items-stretch gap-6 lg:h-[calc(100vh-6.5rem)]">
        
        {/* Left Pane - Chat */}
        <div className="w-full lg:w-[45%] flex flex-col rounded-2xl bg-card border border-border overflow-hidden h-[500px] lg:h-auto lg:min-h-0">
          
          {/* Chat Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 flex items-center justify-center border border-violet-500/20">
                <Sparkles className="w-4 h-4 text-violet-400" />
              </div>
              <span className="text-sm font-semibold text-foreground">Wiz Chat</span>
            </div>
            {messages.length > 0 && (
              <button
                onClick={handleNewChat}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-foreground/60 hover:text-foreground hover:bg-muted transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>New</span>
              </button>
            )}
          </div>

          {/* Transcript Status Banner */}
          {statusError ? (
            <div className="border-b border-border">
              <ErrorState
                compact
                className="py-5"
                title="Unable to check video status"
                message={statusError.message}
                referenceId={statusError.requestId}
                onRetry={retryVideoStatus}
              />
            </div>
          ) : transcriptStatus === 'loading' && (
            <div className="flex items-center justify-center gap-3 px-4 py-3 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 border-b border-border">
              <div className="w-4 h-4 rounded-full border-2 border-violet-400/30 border-t-violet-400 animate-spin" />
              <span className="text-sm text-violet-300">Preparing transcript...</span>
            </div>
          )}
          

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 space-y-4">
              {conversationError && (
                <ErrorState
                  compact
                  title="Unable to start chat"
                  message={conversationError.message}
                  referenceId={conversationError.requestId}
                  onRetry={() => void createNewConversation()}
                />
              )}

              {messages.length === 0 && transcriptStatus === 'ready' && !conversationError && (
                <div className="flex flex-col items-center justify-center text-center py-12 px-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 flex items-center justify-center mb-5 border border-violet-500/20">
                    <Sparkles className="w-8 h-8 text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2 text-foreground">Ready to chat!</h3>
                  <p className="text-foreground/50 text-sm max-w-xs leading-relaxed mb-6">
                    Ask me anything about this video. I'll provide answers with clickable timestamp citations.
                  </p>
                  {videoData?.suggested_questions?.length === 3 && (
                    <div className="flex flex-wrap justify-center gap-2">
                      {videoData.suggested_questions.map((suggestion) => (
                        <button
                          key={suggestion}
                          onClick={() => setInputValue(suggestion)}
                          className="px-3 py-2 text-xs rounded-lg bg-secondary/50 border border-border text-foreground/60 hover:text-foreground hover:bg-secondary hover:border-border/80 transition-all"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {messages.map((message) => {
                // Don't render empty assistant messages (placeholders for streaming)
                if (message.role === 'assistant' && !message.content) return null;

                return (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[70%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-gradient-to-r from-violet-600 to-violet-500 text-white'
                        : 'bg-muted/70 border border-border'
                    }`}
                  >
                    <div className="text-sm leading-loose whitespace-pre-wrap">
                      {message.role === 'assistant'
                        ? parseTimestampCitations(message.content, seekToTimestamp)
                        : parseBoldText(message.content, `user-${message.id}`)}
                    </div>
                  </div>
                </div>
              ); })}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted border border-border rounded-2xl px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-sm text-foreground/50">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-border">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={
                  transcriptStatus === 'ready'
                    ? 'Ask about this video...'
                    : 'Waiting for transcript...'
                }
                disabled={
                  transcriptStatus !== 'ready' ||
                  isLoading ||
                  isCreatingConversation ||
                  Boolean(conversationError)
                }
                className="flex-1 px-4 py-3 bg-muted/50 border border-input rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={
                  transcriptStatus !== 'ready' ||
                  isLoading ||
                  isCreatingConversation ||
                  Boolean(conversationError) ||
                  !inputValue.trim()
                }
                className="px-4 py-3 bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-5 h-5" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Pane - Video + Details */}
        <div className="w-full lg:w-[55%] flex flex-col rounded-2xl bg-card border border-border overflow-hidden">
          {/* Video Player */}
          <div className="relative w-full bg-black flex-shrink-0">
            <div className="aspect-video">
              <iframe
                ref={playerRef}
                src={`https://www.youtube.com/embed/${videoId}?enablejsapi=1&rel=0&modestbranding=1`}
                title="YouTube video player"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="absolute inset-0 w-full h-full"
              />
            </div>
          </div>

          {/* Scrollable Content Area */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Video Title & Channel */}
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-3 flex-1 min-w-0">
                {videoData?.metadata ? (
                  <>
                    <h2 className="text-xl font-bold text-foreground leading-tight">
                      {videoData.title || videoData.metadata.title || 'Untitled Video'}
                    </h2>
                    {/* Channel badge - same style as VideoPage */}
                    <div className="flex flex-wrap items-center gap-2.5">
                      {(videoData.metadata.channel || videoData.metadata.uploader) && (
                        (videoData.metadata.channel_url || videoData.metadata.uploader_url) ? (
                          <a 
                            href={videoData.metadata.channel_url || videoData.metadata.uploader_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-red-500/20 to-red-600/10 text-red-400 border border-red-500/20 hover:from-red-500/30 hover:to-red-600/20 hover:border-red-500/30 transition-all duration-200 cursor-pointer"
                          >
                            {videoData.metadata.channel || videoData.metadata.uploader}
                            <FaExternalLinkAlt className="w-2.5 h-2.5 ml-1.5 opacity-60" />
                          </a>
                        ) : (
                          <span className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-red-500/20 to-red-600/10 text-red-400 border border-red-500/20 select-none">
                            {videoData.metadata.channel || videoData.metadata.uploader}
                          </span>
                        )
                      )}
                      {videoData.metadata.duration_string && (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-sm text-foreground/60 bg-muted/50 border border-border">{videoData.metadata.duration_string}</span>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="h-7 w-3/4 bg-muted rounded-lg animate-pulse" />
                    <div className="h-5 w-1/2 bg-muted rounded-lg animate-pulse" />
                  </>
                )}
              </div>
            </div>

            {/* Metadata Stats - Modern SaaS style */}
            <div className="flex flex-wrap items-center gap-2.5">
              {videoData?.metadata ? (
                <>
                  {typeof videoData.metadata.view_count === 'number' && (
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted/50 border border-border">
                      <svg className="w-3.5 h-3.5 text-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <span className="text-sm font-medium text-foreground/70">
                        {videoData.metadata.view_count.toLocaleString()}
                      </span>
                    </div>
                  )}
                  {typeof videoData.metadata.like_count === 'number' && (
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted/50 border border-border">
                      <svg className="w-3.5 h-3.5 text-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                      </svg>
                      <span className="text-sm font-medium text-foreground/70">
                        {videoData.metadata.like_count.toLocaleString()}
                      </span>
                    </div>
                  )}
                  {videoData.metadata.upload_date && (
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted/50 border border-border">
                      <svg className="w-3.5 h-3.5 text-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span className="text-sm font-medium text-foreground/70">
                        {(() => {
                          // Format YYYYMMDD to readable date
                          const d = videoData.metadata.upload_date;
                          if (d && d.length === 8) {
                            const year = d.slice(0, 4);
                            const month = d.slice(4, 6);
                            const day = d.slice(6, 8);
                            return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            });
                          }
                          return d;
                        })()}
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex gap-3">
                  <div className="h-7 w-20 bg-muted rounded-lg animate-pulse" />
                  <div className="h-7 w-16 bg-muted rounded-lg animate-pulse" />
                  <div className="h-7 w-24 bg-muted rounded-lg animate-pulse" />
                </div>
              )}
            </div>

            {/* AI Summary */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-violet-400" />
                <span className="text-sm font-medium text-foreground/80">AI Summary</span>
              </div>
              {videoData?.summary ? (
                <p className="text-sm text-foreground/60 leading-relaxed">
                  {videoData.summary}
                </p>
              ) : isPolling ? (
                <div className="space-y-2.5">
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                </div>
              ) : (
                <p className="text-sm text-foreground/50 italic">No summary available for this video.</p>
              )}
            </div>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}

export default WizWorkspacePage;
