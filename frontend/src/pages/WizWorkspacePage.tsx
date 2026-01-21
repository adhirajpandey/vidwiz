import { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Send, AlertCircle, Sparkles, RotateCcw } from 'lucide-react';
import WatchYouTubeButton from '../components/WatchYouTubeButton';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: { start_seconds: number; end_seconds?: number; label: string }[];
  createdAt: Date;
}

interface VideoMetadata {
  title: string;
  channel: string;
  duration: string;
  thumbnail: string;
}

/**
 * Parses timestamp citations from message content and makes them clickable
 */
function parseTimestampCitations(content: string, onTimestampClick: (seconds: number) => void): React.ReactNode {
  const timestampRegex = /\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = timestampRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }

    const hours = match[3] ? parseInt(match[1]) : 0;
    const minutes = match[3] ? parseInt(match[2]) : parseInt(match[1]);
    const seconds = match[3] ? parseInt(match[3]) : parseInt(match[2]);
    const totalSeconds = hours * 3600 + minutes * 60 + seconds;

    parts.push(
      <button
        key={match.index}
        onClick={() => onTimestampClick(totalSeconds)}
        className="inline-flex items-center px-2 py-0.5 mx-0.5 rounded-md bg-violet-500/10 text-violet-600 dark:text-violet-300 hover:bg-violet-500/20 transition-all text-sm font-mono border border-violet-500/20"
      >
        {match[0]}
      </button>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.length > 0 ? parts : content;
}

function WizWorkspacePage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [transcriptStatus, setTranscriptStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [metadata, setMetadata] = useState<VideoMetadata | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLIFrameElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setTranscriptStatus('ready');
      setMetadata({
        title: 'Video Title Will Load Here',
        channel: 'Channel Name',
        duration: '12:34',
        thumbnail: `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
      });
    }, 1500);
    return () => clearTimeout(timer);
  }, [videoId]);

  const seekToTimestamp = (seconds: number) => {
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || isLoading || transcriptStatus !== 'ready') return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmed,
      createdAt: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `This is a simulated response to: "${trimmed}"\n\nIn the actual implementation, this would be grounded in the video transcript. For example, the speaker mentions this topic at [2:34] and elaborates further at [5:12].`,
        createdAt: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
      inputRef.current?.focus();
    }, 1500);
  };

  const handleNewChat = () => {
    setMessages([]);
    inputRef.current?.focus();
  };

  return (
    <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-5">
      {/* Main Content - Split View: Chat Left, Video Right */}
      <div className="flex flex-col-reverse lg:flex-row lg:items-stretch gap-6 lg:h-[calc(100vh-6.5rem)]">
        
        {/* Left Pane - Chat */}
        <div className="w-full lg:w-[45%] flex flex-col rounded-2xl bg-card border border-border overflow-hidden min-h-[500px]">
          
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
          {transcriptStatus === 'loading' && (
            <div className="flex items-center justify-center gap-3 px-4 py-3 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 border-b border-border">
              <div className="w-4 h-4 rounded-full border-2 border-violet-400/30 border-t-violet-400 animate-spin" />
              <span className="text-sm text-violet-300">Preparing transcript...</span>
            </div>
          )}
          
          {transcriptStatus === 'error' && (
            <div className="flex items-center justify-center gap-3 px-4 py-3 bg-destructive/10 border-b border-border">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-300">Failed to load transcript</span>
              <button className="ml-2 text-sm text-red-400 hover:text-red-300 underline underline-offset-2">
                Retry
              </button>
            </div>
          )}

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 space-y-4">
              {messages.length === 0 && transcriptStatus === 'ready' && (
                <div className="flex flex-col items-center justify-center text-center py-12 px-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 flex items-center justify-center mb-5 border border-violet-500/20">
                    <Sparkles className="w-8 h-8 text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2 text-foreground">Ready to chat!</h3>
                  <p className="text-foreground/50 text-sm max-w-xs leading-relaxed mb-6">
                    Ask me anything about this video. I'll provide answers with clickable timestamp citations.
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {['Summarize key points', 'What happens at the start?', 'Explain the main topic'].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => setInputValue(suggestion)}
                        className="px-3 py-2 text-xs rounded-lg bg-secondary/50 border border-border text-foreground/60 hover:text-foreground hover:bg-secondary hover:border-border/80 transition-all"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-gradient-to-r from-violet-600 to-violet-500 text-white'
                        : 'bg-muted border border-border'
                    }`}
                  >
                    <div className="text-sm leading-relaxed whitespace-pre-wrap">
                      {message.role === 'assistant'
                        ? parseTimestampCitations(message.content, seekToTimestamp)
                        : message.content}
                    </div>
                  </div>
                </div>
              ))}

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
                disabled={transcriptStatus !== 'ready' || isLoading}
                className="flex-1 px-4 py-3 bg-muted/50 border border-input rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={transcriptStatus !== 'ready' || isLoading || !inputValue.trim()}
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
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Video Title & Channel */}
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2 flex-1 min-w-0">
                {metadata ? (
                  <>
                    <h2 className="text-lg font-semibold text-foreground leading-snug">
                      {metadata.title}
                    </h2>
                    <div className="flex items-center gap-2 text-sm text-foreground/50">
                      <span className="text-foreground/70">{metadata.channel}</span>
                      <span className="w-1 h-1 rounded-full bg-foreground/30" />
                      <span>{metadata.duration}</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="h-6 w-3/4 bg-muted rounded-lg animate-pulse" />
                    <div className="h-4 w-1/2 bg-muted rounded-lg animate-pulse" />
                  </>
                )}
              </div>
              <WatchYouTubeButton videoId={videoId || ''} variant="red" />
            </div>

            {/* Metadata Stats */}
            <div className="flex items-center gap-4 text-sm py-3 border-y border-border">
              {metadata ? (
                <>
                  <div className="flex items-center gap-1.5">
                    <span className="text-foreground/50">Views:</span>
                    <span className="text-foreground/80 font-medium">1.2M</span>
                  </div>
                  <div className="w-px h-4 bg-border" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-foreground/50">Likes:</span>
                    <span className="text-foreground/80 font-medium">45K</span>
                  </div>
                  <div className="w-px h-4 bg-border" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-foreground/50">Published:</span>
                    <span className="text-foreground/80 font-medium">Jan 19, 2026</span>
                  </div>
                </>
              ) : (
                <div className="flex gap-4">
                  <div className="h-4 w-20 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-16 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-24 bg-muted rounded animate-pulse" />
                </div>
              )}
            </div>

            {/* AI Summary */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-violet-400" />
                <span className="text-sm font-medium text-foreground/80">AI Summary</span>
              </div>
              {metadata ? (
                <p className="text-sm text-foreground/60 leading-relaxed">
                  This video provides an in-depth exploration of the latest developments in web development frameworks and modern deployment strategies. The speaker begins by introducing the current landscape of frontend technologies and the challenges developers face when choosing between different solutions. Key topics covered include performance optimizations through edge computing, the evolution of server-side rendering approaches, and how new frameworks are addressing common pain points in developer experience. The discussion also touches on build times, bundle sizes, and the importance of developer tooling in modern web development workflows. Main takeaways include practical recommendations for project architecture, when to choose different rendering strategies, and how to evaluate new technologies for production use cases.
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                  <div className="h-4 w-full bg-muted rounded animate-pulse" />
                  <div className="h-4 w-3/4 bg-muted rounded animate-pulse" />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default WizWorkspacePage;
