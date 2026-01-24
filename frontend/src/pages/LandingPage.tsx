import { useEffect, useState } from 'react';
import { Target, Sparkles, ArrowRight, Play, CheckCircle2, Zap, Brain, ChevronRight, LayoutDashboard, AlertCircle, MessageSquare } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AmbientBackground from '../components/ui/AmbientBackground';
import GradientText from '../components/ui/GradientText';
import GlassCard from '../components/ui/GlassCard';
import config from '../config';

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

function LandingPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsLoggedIn(!!token);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
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

    try {
      const token = localStorage.getItem('token');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${config.API_URL}/wiz/init`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ video_id: videoId }),
      });

      if (!response.ok) {
        throw new Error('Failed to initialize session');
      }

      navigate(`/wiz/${videoId}`);
    } catch (err) {
      console.error('Wiz init error:', err);
      setError('Failed to start session. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden">
      <AmbientBackground />

      <main className="relative pt-20 md:pt-32 pb-20">
        
        {/* HERO SECTION */}
        <section className="max-w-7xl mx-auto px-6 mb-32">
          <div className="flex flex-col items-center text-center">
            
            {/* Badge */}
            <div className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700 select-none">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.15] transition-colors cursor-default">
                <Sparkles className="w-4 h-4 text-amber-400 fill-amber-400/20" />
                <span className="text-sm font-medium text-foreground/80">AI-Powered Video Intelligence</span>
              </div>
            </div>

            {/* Headline */}
            <h1 className="max-w-4xl text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-8 leading-[1.1] animate-in fade-in slide-in-from-bottom-8 duration-1000 select-none">
              Video learning, <br />
              <GradientText>
                truly unlocked.
              </GradientText>
            </h1>

            {/* Subheadline */}
            <p className="max-w-2xl text-lg md:text-xl text-foreground/60 mb-12 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-200 select-none">
              Transform passive watching into active learning. Chat with any video, generate smart notes, 
              and master content 10x faster with AI-powered insights.
            </p>

            {/* Search/Try Wiz Input Section - NEW */}
            <div className="w-full max-w-xl mx-auto mb-16 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
               <div className="relative">
                 {/* Glow behind card - adjusted to be more subtle and red-tinted to match page */}
                 <div className="absolute -inset-1 bg-gradient-to-r from-red-500/10 via-violet-500/10 to-red-500/10 rounded-3xl blur-xl opacity-30"></div>
                 
                 <GlassCard className="relative rounded-2xl p-2 bg-white/[0.03] backdrop-blur-xl border-white/[0.08] shadow-2xl">
                    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
                       <input
                         type="text"
                         value={inputValue}
                         onChange={(e) => {
                           setInputValue(e.target.value);
                           setError(null);
                         }}
                         placeholder="Paste a YouTube link..."
                         className="flex-1 px-5 py-4 bg-white/[0.05] border border-white/[0.1] rounded-xl text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:border-red-500/50 focus:ring-2 focus:ring-red-500/20 transition-all text-base"
                         autoComplete="off"
                       />
                       <button
                         type="submit"
                         disabled={isLoading}
                         className="sm:w-auto min-w-[140px] inline-flex items-center justify-center gap-2 px-6 py-4 text-base font-medium text-white bg-gradient-to-r from-violet-600 to-violet-500 rounded-xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 shadow-[0_0_20px_-5px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_-10px_rgba(139,92,246,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
                       >
                         {isLoading ? (
                           <>
                             <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                             Processing
                           </>
                         ) : (
                           <>
                             Chat with Wiz
                             <Sparkles className="w-4 h-4" />
                           </>
                         )}
                       </button>
                    </form>
                    {error && (
                      <div className="flex items-center gap-2 mt-3 px-2 text-red-400 text-sm animate-in slide-in-from-top-2 fade-in">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        <span>{error}</span>
                      </div>
                    )}
                 </GlassCard>
               </div>
            </div>

            {/* Secondary CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center gap-4 mb-20 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
              <Link 
                to={isLoggedIn ? "/dashboard" : "/signup"} 
                className="w-full sm:w-auto min-w-[180px] inline-flex items-center justify-center gap-2 px-8 py-3 text-sm font-semibold text-foreground/80 bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.15] rounded-xl transition-all duration-300"
              >
                {isLoggedIn ? (
                  <>
                    <LayoutDashboard className="w-4 h-4" />
                    Go to Dashboard
                  </>
                ) : (
                  <>
                    Create Free Account
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </Link>
            </div>

            {/* Github Star Badge */}
            <a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer" className="mb-20 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.05] hover:border-white/[0.1] transition-all group animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-500 cursor-pointer">
              <div className="flex items-center gap-1.5 text-xs font-medium text-foreground/60 group-hover:text-foreground transition-colors">
                 <span>Star this on GitHub</span>
                 <div className="h-3 w-px bg-white/10 mx-1"></div>
                 <span className="flex items-center gap-1 group-hover:text-yellow-400 transition-colors">
                   <Target className="w-3 h-3 fill-current" />
                 </span>
              </div>
            </a>


         </div>
       </section>


        {/* VALUE PROPOSITION GRID */}
        <section id="features" className="max-w-7xl mx-auto px-6 py-24 relative">
           <div className="text-center mb-20 select-none">
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Why <span className="text-red-500">VidWiz</span>?
            </h2>
            <p className="text-xl text-foreground/50 max-w-2xl mx-auto">
              Built for power users who want to extract maximum value from every minute of video.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            
            {/* Feature 1 */}
            <div className="group relative p-8 rounded-3xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden">
               <div className="absolute top-0 right-0 w-32 h-32 bg-red-500/5 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
               <div className="w-14 h-14 bg-red-500/10 rounded-2xl flex items-center justify-center mb-6 text-red-500 group-hover:scale-110 transition-transform duration-300">
                 <MessageSquare className="w-7 h-7" />
               </div>
               <h3 className="text-2xl font-bold mb-3">Context-Aware Chat</h3>
               <p className="text-foreground/60 leading-relaxed">
                 Ask detailed questions and get answers grounded strictly in the video transcript. No hallucinations, just facts.
               </p>
            </div>

            {/* Feature 2 Main */}
            <div className="md:col-span-2 group relative p-8 rounded-3xl bg-gradient-to-br from-violet-500/5 via-fuchsia-500/5 to-transparent border border-white/[0.08] hover:border-violet-500/20 transition-all duration-300 select-none overflow-hidden">
               <div className="absolute inset-0 bg-white/[0.01] group-hover:bg-transparent transition-colors"></div>
               <div className="flex flex-col md:flex-row gap-8 items-start md:items-center h-full">
                 <div className="flex-1">
                   <div className="w-14 h-14 bg-violet-500/10 rounded-2xl flex items-center justify-center mb-6 text-violet-400 group-hover:scale-110 transition-transform duration-300">
                     <Brain className="w-7 h-7" />
                   </div>
                   <h3 className="text-2xl font-bold mb-3">Auto-Summaries & Smart Notes</h3>
                   <p className="text-foreground/60 leading-relaxed mb-6">
                     Need a quick overview? Get instant AI summaries and capture timestamped notes automatically as you watch. Perfect for lectures and tutorials.
                   </p>
                   <div className="flex gap-2">
                     <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 text-violet-300 text-xs font-medium">GPT-4 Powered</span>
                     <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-fuchsia-500/10 text-fuchsia-300 text-xs font-medium">One-Click Notes</span>
                   </div>
                 </div>
                 {/* Visual decoration */}
                 <div className="hidden md:flex flex-1 items-center justify-center">
                   <div className="relative w-48 h-48">
                     <div className="absolute inset-0 bg-gradient-to-tr from-violet-500 to-fuchsia-500 rounded-full blur-[60px] opacity-20 animate-pulse"></div>
                     <div className="relative z-10 p-6 rounded-2xl bg-black/40 backdrop-blur-xl border border-white/10 rotate-3 group-hover:rotate-0 transition-transform duration-500">
                        <div className="h-2 w-24 bg-white/20 rounded mb-4"></div>
                        <div className="space-y-2">
                          <div className="h-2 w-full bg-white/10 rounded"></div>
                          <div className="h-2 w-full bg-white/10 rounded"></div>
                          <div className="h-2 w-2/3 bg-white/10 rounded"></div>
                        </div>
                     </div>
                   </div>
                 </div>
               </div>
            </div>

            {/* Feature 3 */}
            <div className="group relative p-8 rounded-3xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden">
               <div className="absolute bottom-0 right-0 w-32 h-32 bg-blue-500/5 rounded-tl-full -mr-8 -mb-8 transition-transform group-hover:scale-110"></div>
               <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 text-blue-500 group-hover:scale-110 transition-transform duration-300">
                 <Target className="w-7 h-7" />
               </div>
               <h3 className="text-2xl font-bold mb-3">Precision Timestamps</h3>
               <p className="text-foreground/60 leading-relaxed">
                 Every note and chat answer links to the exact second. Click a citation or note to jump straight to the source.
               </p>
            </div>

             {/* Feature 4 */}
            <div className="md:col-span-2 group relative p-8 rounded-3xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden">
               <div className="flex flex-col md:flex-row gap-8 items-center h-full">
                 <div className="flex-1">
                   <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 text-emerald-500 group-hover:scale-110 transition-transform duration-300">
                     <Zap className="w-7 h-7" />
                   </div>
                   <h3 className="text-2xl font-bold mb-3">Unified Knowledge Hub</h3>
                   <p className="text-foreground/60 leading-relaxed">
                     Your central workspace. Save your chats, organize your notes, and build a searchable video knowledge base that syncs across devices.
                   </p>
                 </div>
               </div>
            </div>

          </div>
        </section>


        {/* HOW IT WORKS */}
        <section id="how-it-works" className="max-w-7xl mx-auto px-6 py-24 select-none">
          <div className="flex flex-col md:flex-row items-end justify-between mb-16 gap-6">
            <div>
              <h2 className="text-4xl md:text-5xl font-bold mb-4">Zero Friction Workflow</h2>
              <p className="text-xl text-foreground/50">From installation to mastery in three steps.</p>
            </div>
            <Link to={isLoggedIn ? "/dashboard" : "/signup"} className="text-red-400 hover:text-red-300 font-medium flex items-center gap-2 group">
              {isLoggedIn ? "Open Dashboard" : "Get Started Now"} <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connecting Line (Desktop) */}
            <div className="hidden md:block absolute top-12 left-[16%] right-[16%] h-0.5 bg-gradient-to-r from-red-500/0 via-red-500/20 to-red-500/0"></div>

            {[
              { num: '01', title: 'Bring Any Video', desc: 'Paste a YouTube link or use our browser extension to start instantly.' },
              { num: '02', title: 'Interact & Capture', desc: 'Chat with Wiz for deep answers, or generate one-click summaries and notes.' },
              { num: '03', title: 'Master Content', desc: 'Review your timestamped insights and curated knowledge hub.' }
            ].map((step, i) => (
              <div key={i} className="relative pt-8 group">
                <div className="w-8 h-8 rounded-full bg-background border-4 border-red-500/20 mx-auto absolute top-8 left-1/2 -translate-x-1/2 -translate-y-1/2 md:-translate-y-0 md:top-0 z-10 group-hover:border-red-500/50 transition-colors">
                  <div className="w-full h-full rounded-full bg-red-500 scale-50"></div>
                </div>
                <div className="text-center p-6 rounded-2xl bg-white/[0.01] hover:bg-white/[0.03] border border-transparent hover:border-white/[0.05] transition-all duration-300">
                  <div className="text-4xl font-bold text-white/10 mb-4 font-mono">{step.num}</div>
                  <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                  <p className="text-foreground/50 text-sm leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>


        {/* FINAL CTA */}
        <section className="max-w-5xl mx-auto px-6 py-24">
          <div className="relative rounded-[2.5rem] overflow-hidden p-12 md:p-24 text-center select-none group bg-white/[0.02] border border-white/[0.08]">
            
            {/* Ambient background glow - Subtler */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-500/10 rounded-full blur-[120px] pointer-events-none"></div>

            <div className="relative z-10">
              <h2 className="text-4xl md:text-6xl font-bold text-foreground mb-8 tracking-tight">
                Ready to stop watching <br/> and start learning?
              </h2>
              <p className="text-xl text-foreground/60 mb-12 max-w-2xl mx-auto">
                Join the community of developers, students, and lifelong learners using VidWiz to build their second brain.
              </p>
              
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link 
                  to="/wiz" 
                  className="min-w-[200px] px-8 py-4 bg-gradient-to-r from-violet-600 to-violet-500 text-white rounded-xl font-bold text-lg hover:bg-violet-600 transition-all transform hover:-translate-y-1 shadow-lg hover:shadow-violet-500/25 inline-flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-5 h-5" />
                  Chat with Wiz
                </Link>

                <Link 
                  to={isLoggedIn ? "/dashboard" : "/signup"} 
                  className="min-w-[200px] px-8 py-4 bg-gradient-to-r from-red-600 to-red-500 text-white rounded-xl font-bold text-lg hover:bg-red-600 transition-all transform hover:-translate-y-1 shadow-lg hover:shadow-red-500/25 inline-flex items-center justify-center gap-2"
                >
                  {isLoggedIn ? (
                    <>
                      <LayoutDashboard className="w-5 h-5" />
                      Open Dashboard
                    </>
                  ) : (
                    "Get Started for Free"
                  )}
                </Link>
              </div>
              
              <div className="flex items-center justify-center gap-2 text-foreground/60 mt-6">
                <CheckCircle2 className="w-5 h-5 text-red-500" />
                <span className="text-sm font-medium">No credit card required</span>
              </div>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}

export default LandingPage;
