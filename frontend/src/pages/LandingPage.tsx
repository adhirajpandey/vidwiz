import { useEffect, useState } from 'react';
import { Target, Sparkles, ArrowRight, CheckCircle2, Zap, Brain, LayoutDashboard, AlertCircle, MessageSquare, Star } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AmbientBackground from '../components/ui/AmbientBackground';
import config from '../config';
import { isAuthenticated, getAuthHeaders } from '../lib/authUtils';

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
    setIsLoggedIn(isAuthenticated());
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
      const response = await fetch(`${config.API_URL}/wiz/init`, {
        method: 'POST',
        headers: getAuthHeaders(),
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

      <main className="relative z-10 pt-12 md:pt-24 pb-12 md:pb-20">
        
        {/* HERO SECTION */}
        <section className="max-w-7xl mx-auto px-4 md:px-6 mb-12 md:mb-24 relative">
          {/* Floating Orbs - Modern SaaS aesthetic */}
          <div className="absolute -top-20 -left-20 w-72 h-72 bg-violet-500/30 rounded-full blur-[100px] animate-pulse pointer-events-none" />
          <div className="absolute -top-10 -right-20 w-64 h-64 bg-red-500/20 rounded-full blur-[100px] animate-pulse pointer-events-none" style={{ animationDelay: '1s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-fuchsia-500/10 rounded-full blur-[120px] pointer-events-none" />
          
          <div className="flex flex-col items-center text-center relative z-10">
            
            {/* Top Badge - Simplified */}
            <div className="mb-4 md:mb-6 animate-in fade-in slide-in-from-bottom-4 duration-700 select-none">
              <div className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-full cursor-default">
                {/* Gradient border effect */}
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-violet-500/50 via-fuchsia-500/50 to-red-500/50 opacity-20 group-hover:opacity-40 transition-opacity" />
                <div className="absolute inset-[1px] rounded-full bg-white/90 dark:bg-black/80 backdrop-blur-xl" />
                <div className="relative flex items-center gap-2">
                  <div className="relative">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
                    <div className="absolute inset-0 w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  </div>
                  <span className="text-xs font-bold text-gray-800 dark:text-foreground/90 tracking-wide uppercase">v1.0 Live</span>
                </div>
              </div>
            </div>

            {/* Headline - Restored Brand Copy & Gradient */}
            <h1 className="max-w-6xl text-[2.75rem] md:text-8xl font-bold tracking-tighter mb-4 md:mb-8 leading-[1.05] animate-in fade-in slide-in-from-bottom-8 duration-1000 select-none">
              Video learning, <br />
              <span className="bg-gradient-to-r from-violet-500 via-fuchsia-500 to-red-500 bg-clip-text text-transparent bg-[length:200%_auto] animate-gradient drop-shadow-[0_0_30px_rgba(139,92,246,0.3)]">
                truly unlocked.
              </span>
            </h1>

            {/* Subheadline - Restored Value Prop */}
            <p className="max-w-3xl text-base md:text-2xl text-gray-600 dark:text-foreground/60 mb-8 md:mb-16 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-200 select-none font-light">
              Transform passive watching into active learning. Chat with any video, generate smart notes, 
              and master content 10x faster.
            </p>

            {/* Search/Try Wiz Input Section - Modern SaaS Style */}
            <div className="w-full max-w-xl mx-auto mb-6 md:mb-12 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300 group">
               <div className="relative">
                 {/* Animated gradient border */}
                 <div className="absolute -inset-[1px] bg-gradient-to-r from-violet-600 via-fuchsia-500 to-red-500 rounded-3xl sm:rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-sm" />
                 <div className="absolute -inset-[1px] bg-gradient-to-r from-violet-600 via-fuchsia-500 to-red-500 rounded-3xl sm:rounded-full opacity-20 group-hover:opacity-50 transition-opacity duration-500" />
                 
                 {/* Glow effect */}
                 <div className="absolute -inset-4 bg-gradient-to-r from-violet-600/20 via-fuchsia-500/20 to-red-500/20 rounded-3xl sm:rounded-full blur-2xl opacity-0 group-hover:opacity-60 transition-opacity duration-500" />
                 
                 <div className="relative rounded-3xl sm:rounded-full p-4 sm:p-2 bg-white/95 dark:bg-gray-950/90 backdrop-blur-xl border border-gray-200/50 dark:border-white/[0.05] shadow-2xl transition-all duration-300">
                    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 sm:gap-2">
                       <input
                         type="text"
                         value={inputValue}
                         onChange={(e) => {
                           setInputValue(e.target.value);
                           setError(null);
                         }}
                         placeholder="Paste a YouTube link to start..."
                         className="flex-1 px-4 md:px-6 py-3 md:py-4 bg-transparent border-none text-gray-900 dark:text-foreground placeholder:text-gray-400 dark:placeholder:text-muted-foreground/50 focus:outline-none focus:ring-0 text-base md:text-lg"
                         autoComplete="off"
                       />
                       <button
                          type="submit"
                          disabled={isLoading}
                          className="relative overflow-hidden w-full sm:w-auto min-w-[160px] inline-flex items-center justify-center gap-2 px-6 md:px-8 py-3 md:py-4 text-sm md:text-base font-bold text-white bg-gradient-to-r from-violet-600 via-violet-500 to-fuchsia-500 rounded-full hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_2s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent"
                       >
                         {isLoading ? (
                           <>
                             <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                             Processing
                           </>
                         ) : (
                           <>
                             Chat with Wiz
                             <ArrowRight className="w-4 h-4" />
                           </>
                         )}
                       </button>
                    </form>
                 </div>
                 
               </div>
                  {error && (
                    <div className="flex items-center justify-center gap-2 mt-4 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 text-sm font-medium animate-in slide-in-from-top-2 fade-in backdrop-blur-sm">
                      <AlertCircle className="w-4 h-4 text-red-400" />
                      <span>{error}</span>
                    </div>
                  )}
            </div>

            {/* GitHub Star - Prominent */}
            <div className="animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-500">
              <a 
                href="https://github.com/adhirajpandey/vidwiz" 
                target="_blank" 
                rel="noopener noreferrer"
                className="group relative inline-flex items-center gap-3 px-6 py-3 rounded-full text-sm font-semibold transition-all duration-300 hover:scale-105"
              >
                {/* Gradient glow on hover */}
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-amber-500/30 to-yellow-500/30 opacity-0 group-hover:opacity-100 blur-xl transition-opacity" />
                {/* Background layers */}
                <div className="absolute inset-0 rounded-full bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] group-hover:border-yellow-500/40 transition-colors" />
                
                <div className="relative flex items-center gap-2">
                  <Star className="w-5 h-5 text-foreground/60 group-hover:text-yellow-400 group-hover:fill-yellow-400 transition-all duration-300" />
                  <span className="text-foreground/80 group-hover:text-foreground transition-colors">Star on GitHub</span>
                </div>
              </a>
            </div>

         </div>
       </section>


        {/* VALUE PROPOSITION GRID */}
        <section id="features" className="max-w-7xl mx-auto px-4 md:px-6 py-16 md:py-24 relative">
           <div className="text-center mb-12 md:mb-16 select-none relative">
            <h2 className="text-3xl md:text-5xl font-bold mb-4 relative z-10">
              Why <span className="bg-gradient-to-r from-red-500 via-fuchsia-500 to-violet-500 bg-clip-text text-transparent">VidWiz</span>?
            </h2>
            <p className="text-base md:text-xl text-gray-500 dark:text-foreground/50 max-w-2xl mx-auto relative z-10">
              Built for power users who want to extract maximum value from every minute of video.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            
            {/* Feature 1 */}
            <div className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-violet-200 dark:hover:border-violet-500/20 transition-all duration-300 select-none">
               <div className="w-12 h-12 bg-violet-500/10 rounded-xl flex items-center justify-center mb-4 text-violet-500 group-hover:scale-110 transition-transform duration-300">
                 <MessageSquare className="w-6 h-6" />
               </div>
               <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">Chat with Wiz</h3>
               <p className="text-sm text-gray-500 dark:text-foreground/50 leading-relaxed">
                 Ask detailed questions and get answers grounded in the transcript.
               </p>
            </div>

            {/* Feature 2 */}
            <div className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-red-200 dark:hover:border-red-500/20 transition-all duration-300 select-none">
               <div className="w-12 h-12 bg-red-500/10 rounded-xl flex items-center justify-center mb-4 text-red-500 group-hover:scale-110 transition-transform duration-300">
                 <Brain className="w-6 h-6" />
               </div>
               <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">AI Summaries</h3>
               <p className="text-sm text-gray-500 dark:text-foreground/50 leading-relaxed">
                 Get instant summaries and timestamped notes automatically.
               </p>
            </div>

            {/* Feature 3 */}
            <div className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-fuchsia-200 dark:hover:border-fuchsia-500/20 transition-all duration-300 select-none">
               <div className="w-12 h-12 bg-fuchsia-500/10 rounded-xl flex items-center justify-center mb-4 text-fuchsia-500 group-hover:scale-110 transition-transform duration-300">
                 <Target className="w-6 h-6" />
               </div>
               <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">Timestamps</h3>
               <p className="text-sm text-gray-500 dark:text-foreground/50 leading-relaxed">
                 Jump to the exact second in the video with precision links.
               </p>
            </div>

            {/* Feature 4 */}
            <div className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-amber-200 dark:hover:border-amber-500/20 transition-all duration-300 select-none">
               <div className="w-12 h-12 bg-amber-500/10 rounded-xl flex items-center justify-center mb-4 text-amber-500 group-hover:scale-110 transition-transform duration-300">
                 <Zap className="w-6 h-6" />
               </div>
               <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">Knowledge Hub</h3>
               <p className="text-sm text-gray-500 dark:text-foreground/50 leading-relaxed">
                 Save chats, organize notes, and search your video library.
               </p>
            </div>

          </div>
        </section>


        {/* HOW IT WORKS */}
        <section id="how-it-works" className="max-w-7xl mx-auto px-4 md:px-6 py-16 md:py-24 select-none">
          
          <div className="text-center mb-12 md:mb-16">
            <h2 className="text-3xl md:text-5xl font-bold mb-4 text-gray-900 dark:text-white">How It Works</h2>
            <p className="text-base md:text-xl text-gray-500 dark:text-foreground/50">Two powerful ways to master any video.</p>
          </div>

          {/* WORKFLOW 1: WIZ (Chat) */}
          <div className="mb-16 md:mb-20">
             <div className="flex items-center gap-3 mb-8 justify-center md:justify-start">
               <div className="p-2 bg-violet-500/10 rounded-lg">
                 <Sparkles className="w-5 h-5 text-violet-500" />
               </div>
               <h3 className="text-xl font-bold text-gray-900 dark:text-white">Interactive Chat</h3>
             </div>
             
             <div className="grid md:grid-cols-3 gap-4 md:gap-6">
                {[
                  { num: '01', title: 'Paste Link', desc: 'Drop a YouTube URL to initialize Wiz.' },
                  { num: '02', title: 'Ask Questions', desc: 'Challenge Wiz with any question about the content.' },
                  { num: '03', title: 'Get Answers', desc: 'Receive answers with timestamps to the source.' }
                ].map((step, i) => (
                  <div key={i} className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-violet-200 dark:hover:border-violet-500/20 transition-all duration-300">
                    <div className="text-3xl font-bold text-violet-500/30 dark:text-violet-400/30 mb-3 font-mono">{step.num}</div>
                    <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">{step.title}</h3>
                    <p className="text-sm text-gray-500 dark:text-foreground/50">{step.desc}</p>
                  </div>
                ))}
             </div>
          </div>

          {/* WORKFLOW 2: NOTES (Capture) */}
          <div>
             <div className="flex items-center gap-3 mb-8 justify-center md:justify-start">
               <div className="p-2 bg-red-500/10 rounded-lg">
                 <Brain className="w-5 h-5 text-red-500" />
               </div>
               <h3 className="text-xl font-bold text-gray-900 dark:text-white">Smart Note Taking</h3>
             </div>

             <div className="grid md:grid-cols-3 gap-4 md:gap-6">
                {[
                  { num: '01', title: 'Watch Video', desc: 'Watch any YouTube video in your browser.' },
                  { num: '02', title: 'Generate Notes', desc: 'Click once to capture AI-powered notes.' },
                  { num: '03', title: 'Build Library', desc: 'Review, search, and export your knowledge.' }
                ].map((step, i) => (
                  <div key={i} className="group p-6 rounded-2xl bg-white/50 dark:bg-white/[0.02] border border-gray-100 dark:border-white/[0.06] hover:border-red-200 dark:hover:border-red-500/20 transition-all duration-300">
                    <div className="text-3xl font-bold text-red-500/30 dark:text-red-400/30 mb-3 font-mono">{step.num}</div>
                    <h3 className="text-lg font-bold mb-2 text-gray-900 dark:text-white">{step.title}</h3>
                    <p className="text-sm text-gray-500 dark:text-foreground/50">{step.desc}</p>
                  </div>
                ))}
             </div>
          </div>

        </section>


        {/* FINAL CTA */}
        <section className="max-w-4xl mx-auto px-4 md:px-6 py-16 md:py-24">
          <div className="relative rounded-2xl md:rounded-3xl overflow-hidden p-8 md:p-16 text-center select-none group">
            
            {/* Gradient border */}
            <div className="absolute inset-0 bg-gradient-to-br from-violet-500/20 via-fuchsia-500/20 to-red-500/20 rounded-2xl md:rounded-3xl" />
            <div className="absolute inset-[1px] bg-white dark:bg-gray-950 rounded-2xl md:rounded-3xl" />
            
            {/* Ambient glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-gradient-to-br from-violet-500/10 via-fuchsia-500/10 to-red-500/10 rounded-full blur-[80px] pointer-events-none" />

            <div className="relative z-10">
              <h2 className="text-2xl md:text-5xl font-bold text-gray-900 dark:text-white mb-4 md:mb-6 tracking-tight">
                Ready to start learning?
              </h2>
              <p className="text-base md:text-lg text-gray-500 dark:text-foreground/50 mb-8 max-w-lg mx-auto">
                Join developers, students, and lifelong learners using <span className="bg-gradient-to-r from-red-500 to-violet-500 bg-clip-text text-transparent font-semibold">VidWiz</span>.
              </p>
              
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link 
                  to="/wiz" 
                  className="w-full sm:w-auto px-6 py-3 bg-white dark:bg-white/[0.05] border border-gray-200 dark:border-white/[0.1] text-gray-900 dark:text-white hover:border-violet-300 dark:hover:border-violet-500/30 rounded-xl font-semibold transition-all inline-flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-4 h-4 text-violet-500" />
                  Try Wiz
                </Link>

                <Link 
                  to={isLoggedIn ? "/dashboard" : "/signup"} 
                  className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-red-600 via-red-500 to-red-600 text-white rounded-xl font-semibold transition-all hover:bg-right duration-500 shadow-lg shadow-red-500/20 hover:shadow-red-500/30 inline-flex items-center justify-center gap-2 bg-[length:200%_100%]"
                >
                  {isLoggedIn ? (
                    <>
                      <LayoutDashboard className="w-4 h-4" />
                      Dashboard
                    </>
                  ) : (
                    "Get Started"
                  )}
                </Link>
              </div>
              
              <div className="flex items-center justify-center gap-2 text-gray-400 dark:text-foreground/40 mt-6">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-xs font-medium">No credit card required</span>
              </div>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}

export default LandingPage;
