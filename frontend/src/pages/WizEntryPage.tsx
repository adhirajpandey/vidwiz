import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, MessageSquare, Clock, Brain, AlertCircle } from 'lucide-react';
import AmbientBackground from '../components/ui/AmbientBackground';
import GradientText from '../components/ui/GradientText';
import GlassCard from '../components/ui/GlassCard';

/**
 * Extracts a YouTube video ID from various URL formats or raw ID.
 * Returns null if invalid or if it's a playlist URL.
 */
function extractVideoId(input: string): string | null {
  const trimmed = input.trim();
  
  if (!trimmed) return null;
  
  // Reject playlist URLs
  if (trimmed.includes('list=')) {
    return null;
  }
  
  // Check if it's a raw video ID (11 characters, alphanumeric with - and _)
  const rawIdPattern = /^[a-zA-Z0-9_-]{11}$/;
  if (rawIdPattern.test(trimmed)) {
    return trimmed;
  }
  
  try {
    const url = new URL(trimmed);
    const hostname = url.hostname.replace('www.', '');
    
    // youtube.com/watch?v=VIDEO_ID
    if (hostname === 'youtube.com' && url.pathname === '/watch') {
      const videoId = url.searchParams.get('v');
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/shorts/VIDEO_ID
    if (hostname === 'youtube.com' && url.pathname.startsWith('/shorts/')) {
      const videoId = url.pathname.split('/shorts/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/live/VIDEO_ID
    if (hostname === 'youtube.com' && url.pathname.startsWith('/live/')) {
      const videoId = url.pathname.split('/live/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/embed/VIDEO_ID
    if (hostname === 'youtube.com' && url.pathname.startsWith('/embed/')) {
      const videoId = url.pathname.split('/embed/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtu.be/VIDEO_ID
    if (hostname === 'youtu.be') {
      const videoId = url.pathname.slice(1).split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
  } catch {
    // Not a valid URL, already checked for raw ID above
    return null;
  }
  
  return null;
}

function WizEntryPage() {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    const trimmed = inputValue.trim();
    
    if (!trimmed) {
      setError('Please enter a YouTube URL or video ID');
      return;
    }
    
    // Check for playlist URL
    if (trimmed.includes('list=')) {
      setError('Playlist URLs are not supported. Please enter a single video URL.');
      return;
    }
    
    const videoId = extractVideoId(trimmed);
    
    if (!videoId) {
      setError('Invalid YouTube URL or video ID. Please check and try again.');
      return;
    }
    
    setIsLoading(true);
    navigate(`/wiz/${videoId}`);
  };

  return (
    <div className="relative min-h-screen overflow-hidden">
      <AmbientBackground />

      <main className="relative pt-20 md:pt-32 pb-20">
        
        {/* HERO SECTION */}
        <section className="max-w-4xl mx-auto px-6 mb-16">
          <div className="flex flex-col items-center text-center">
            
            {/* Badge */}
            <div className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700 select-none">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.15] transition-colors cursor-default">
                <Sparkles className="w-4 h-4 text-violet-400 fill-violet-400/20" />
                <span className="text-sm font-medium text-foreground/80">AI-Powered Video Chat</span>
              </div>
            </div>

            {/* Headline */}
            <h1 className="max-w-3xl text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 leading-[1.1] animate-in fade-in slide-in-from-bottom-8 duration-1000 select-none">
              Meet{' '}
              <GradientText>
                Wiz
              </GradientText>
            </h1>

            {/* Subheadline */}
            <p className="max-w-2xl text-lg md:text-xl text-foreground/60 mb-12 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-200 select-none">
              Your AI companion for mastering YouTube videos. Ask questions, get timestamped answers, 
              and dive deep into any video's content.
            </p>

            {/* Input Card */}
            <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
              <div className="relative">
                {/* Glow behind card */}
                <div className="absolute -inset-1 bg-gradient-to-r from-violet-500/20 via-red-500/20 to-violet-500/20 rounded-3xl blur-xl opacity-50"></div>
                
                <GlassCard className="relative rounded-2xl md:rounded-3xl p-6 md:p-8 bg-black/60 border-white/10">
                  <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                      <label htmlFor="video-input" className="block text-sm font-medium text-foreground/70 mb-3 text-left">
                        Enter a YouTube video URL or ID
                      </label>
                      <input
                        id="video-input"
                        type="text"
                        value={inputValue}
                        onChange={(e) => {
                          setInputValue(e.target.value);
                          setError(null);
                        }}
                        placeholder="https://youtube.com/watch?v=... or video ID"
                        className="w-full px-5 py-4 bg-white/[0.03] border border-white/[0.08] rounded-xl text-foreground placeholder:text-foreground/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 transition-all"
                        autoComplete="off"
                        autoFocus
                      />
                      {error && (
                        <div className="flex items-center gap-2 mt-3 text-red-400 text-sm">
                          <AlertCircle className="w-4 h-4 flex-shrink-0" />
                          <span>{error}</span>
                        </div>
                      )}
                    </div>
                    
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="w-full inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-violet-600 to-violet-500 rounded-xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 shadow-[0_0_40px_-10px_rgba(139,92,246,0.4)] hover:shadow-[0_0_60px_-15px_rgba(139,92,246,0.6)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                    >
                      {isLoading ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                          Loading...
                        </>
                      ) : (
                        <>
                          Start Chat
                          <ArrowRight className="w-5 h-5" />
                        </>
                      )}
                    </button>
                  </form>
                  
                  {/* Supported formats hint */}
                  <div className="mt-6 pt-6 border-t border-white/[0.05]">
                    <p className="text-xs text-foreground/40 text-center">
                      Supports youtube.com, youtu.be, Shorts, Live, and direct video IDs
                    </p>
                  </div>
                </GlassCard>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURES SECTION */}
        <section className="max-w-4xl mx-auto px-6 py-16">
          <div className="grid md:grid-cols-3 gap-6">
            
            {/* Feature 1 */}
            <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none">
              <div className="w-12 h-12 bg-violet-500/10 rounded-xl flex items-center justify-center mb-4 text-violet-400 group-hover:scale-110 transition-transform duration-300">
                <MessageSquare className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold mb-2">Grounded Answers</h3>
              <p className="text-foreground/50 text-sm leading-relaxed">
                Every response is backed by the video transcript. No hallucinations, just facts.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none">
              <div className="w-12 h-12 bg-red-500/10 rounded-xl flex items-center justify-center mb-4 text-red-400 group-hover:scale-110 transition-transform duration-300">
                <Clock className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold mb-2">Timestamp Citations</h3>
              <p className="text-foreground/50 text-sm leading-relaxed">
                Click any timestamp to jump directly to that moment in the video.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none">
              <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-4 text-emerald-400 group-hover:scale-110 transition-transform duration-300">
                <Brain className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold mb-2">Deep Understanding</h3>
              <p className="text-foreground/50 text-sm leading-relaxed">
                Ask complex questions and get intelligent, context-aware responses.
              </p>
            </div>

          </div>
        </section>

      </main>
    </div>
  );
}

export default WizEntryPage;
