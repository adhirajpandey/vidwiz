import { useEffect, useState } from 'react';
import { Target, Sparkles, ArrowRight, CheckCircle2, Zap, Brain, LayoutDashboard, AlertCircle, MessageSquare, ChevronRight, Star } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AmbientBackground from '../components/ui/AmbientBackground';
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

      <main className="relative z-10 pt-20 md:pt-24 pb-20">
        
        {/* HERO SECTION */}
        <section className="max-w-7xl mx-auto px-6 mb-24">
          <div className="flex flex-col items-center text-center">
            
            {/* Top Badge - Simplified */}
            <div className="mb-6 animate-in fade-in slide-in-from-bottom-4 duration-700 select-none">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.08] backdrop-blur-sm cursor-default hover:border-violet-500/20 transition-colors shadow-sm dark:shadow-none">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)] animate-pulse"></div>
                  <span className="text-xs font-bold text-gray-800 dark:text-foreground/80 tracking-wide">v1.0 Live</span>
              </div>
            </div>

            {/* Headline - Restored Brand Copy & Gradient */}
            <h1 className="max-w-6xl text-6xl md:text-8xl font-bold tracking-tighter mb-8 leading-[1.05] animate-in fade-in slide-in-from-bottom-8 duration-1000 select-none">
              Video learning, <br />
              <span className="bg-gradient-to-r from-violet-500 via-fuchsia-500 to-red-500 bg-clip-text text-transparent bg-[length:200%_auto] animate-gradient drop-shadow-[0_0_30px_rgba(139,92,246,0.3)]">
                truly unlocked.
              </span>
            </h1>

            {/* Subheadline - Restored Value Prop */}
            <p className="max-w-3xl text-xl md:text-2xl text-gray-600 dark:text-foreground/60 mb-16 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-200 select-none font-light">
              Transform passive watching into active learning. Chat with any video, generate smart notes, 
              and master content 10x faster.
            </p>

            {/* Search/Try Wiz Input Section - Restored Violet Theme */}
            <div className="w-full max-w-xl mx-auto mb-12 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300 group">
               <div className="relative">
                 {/* Glow - Restored Violet/Red */}
                 <div className="absolute -inset-1 bg-gradient-to-r from-violet-600/20 via-red-500/20 to-violet-600/20 rounded-full blur-2xl opacity-30 group-hover:opacity-60 transition-opacity duration-500"></div>
                 
                 <div className="relative rounded-full p-2 bg-white/80 dark:bg-black/40 backdrop-blur-xl border border-gray-200 dark:border-white/[0.08] shadow-2xl transition-all duration-300 group-hover:border-violet-500/30">
                    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
                       <input
                         type="text"
                         value={inputValue}
                         onChange={(e) => {
                           setInputValue(e.target.value);
                           setError(null);
                         }}
                         placeholder="Paste a YouTube link to start..."
                         className="flex-1 px-6 py-4 bg-transparent border-none text-gray-900 dark:text-foreground placeholder:text-gray-500 dark:placeholder:text-muted-foreground/60 focus:outline-none focus:ring-0 text-lg"
                         autoComplete="off"
                       />
                       <button
                         type="submit"
                         disabled={isLoading}
                         className="sm:w-auto min-w-[160px] inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-bold text-white bg-gradient-to-r from-violet-600 to-violet-500 rounded-full hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_20px_-5px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_-10px_rgba(139,92,246,0.5)]"
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
                 
                 {error && (
                   <div className="flex items-center justify-center gap-2 mt-4 text-red-400 text-sm animate-in slide-in-from-top-2 fade-in">
                     <AlertCircle className="w-4 h-4" />
                     <span>{error}</span>
                   </div>
                 )}
               </div>
            </div>

            {/* Secondary Actions Row */}
            <div className="flex flex-col items-center gap-3 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-500 w-full max-w-sm mx-auto">
              {/* Secondary CTA */}
              <Link 
                to={isLoggedIn ? "/dashboard" : "/signup"} 
                className="group flex items-center gap-2 px-6 py-3 rounded-full bg-accent/50 dark:bg-white/[0.03] hover:bg-accent dark:hover:bg-white/[0.08] border border-gray-200 dark:border-white/[0.08] hover:border-violet-500/30 transition-all duration-300 w-full justify-center"
              >
                <div className="p-1 rounded-full bg-violet-100 dark:bg-white/[0.05] group-hover:bg-violet-200 dark:group-hover:bg-violet-500/20 transition-colors">
                  {isLoggedIn ? <LayoutDashboard className="w-4 h-3.5 text-violet-600 dark:text-violet-300" /> : <Zap className="w-4 h-3.5 text-violet-600 dark:text-violet-300" />}
                </div>
                <span className="text-sm font-semibold text-gray-800 dark:text-foreground/80 group-hover:text-gray-900 dark:group-hover:text-foreground transition-colors">
                  {isLoggedIn ? "Open Dashboard" : "Start Smart Note Taking"}
                </span>
                {!isLoggedIn && <ChevronRight className="w-3.5 h-3.5 text-gray-500 dark:text-foreground/40 group-hover:translate-x-0.5 transition-transform" />}
              </Link>

              {/* GitHub Star */}
              <a 
                href="https://github.com/adhirajpandey/vidwiz" 
                target="_blank" 
                rel="noopener noreferrer"
                className="group flex items-center gap-2 px-6 py-3 rounded-full bg-accent/50 dark:bg-white/[0.03] hover:bg-accent dark:hover:bg-white/[0.08] border border-gray-200 dark:border-white/[0.08] hover:border-yellow-500/30 transition-all duration-300 w-full justify-center"
              >
                 <Star className="w-4 h-3.5 text-gray-500 dark:text-foreground/60 group-hover:text-yellow-500 dark:group-hover:text-yellow-400 group-hover:fill-yellow-500 dark:group-hover:fill-yellow-400 transition-all duration-300" />
                 <span className="text-sm font-semibold text-gray-700 dark:text-foreground/80 group-hover:text-gray-900 dark:group-hover:text-foreground transition-colors">Star on GitHub</span>
              </a>
            </div>

         </div>
       </section>


        {/* VALUE PROPOSITION GRID */}
        <section id="features" className="max-w-7xl mx-auto px-6 py-16 relative">
           <div className="text-center mb-12 select-none relative">
            {/* Subtle Title Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-20 bg-red-500/20 blur-[60px] pointer-events-none"></div>
            <h2 className="text-4xl md:text-5xl font-bold mb-6 relative z-10">
              Why <span className="text-red-500">VidWiz</span>?
            </h2>
            <p className="text-xl text-foreground/50 max-w-2xl mx-auto relative z-10">
              Built for power users who want to extract maximum value from every minute of video.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            
            {/* Feature 1 */}
            <div className="group relative p-8 rounded-3xl bg-white dark:bg-white/[0.02] border border-gray-200 dark:border-white/[0.08] shadow-lg shadow-gray-200/80 dark:shadow-none hover:border-violet-200 dark:hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden hover:shadow-xl hover:shadow-violet-500/10 dark:hover:shadow-[0_0_30px_-10px_rgba(255,255,255,0.05)]">
               <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
               <div className="w-14 h-14 bg-violet-500/10 rounded-2xl flex items-center justify-center mb-6 text-violet-500 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_-5px_rgba(139,92,246,0.2)]">
                 <MessageSquare className="w-7 h-7" />
               </div>
               <h3 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">Chat with Wiz</h3>
               <p className="text-gray-600 dark:text-foreground/60 leading-relaxed">
                 Meet Wiz, your AI video companion. Ask detailed questions and get answers grounded strictly in the transcript.
               </p>
            </div>

            {/* Feature 2 Main */}
            <div className="md:col-span-2 group relative p-8 rounded-3xl bg-gradient-to-br from-red-50/80 via-white to-white dark:from-red-500/5 dark:via-orange-500/5 dark:to-transparent border border-red-100 dark:border-white/[0.08] shadow-xl shadow-red-100/50 dark:shadow-none hover:border-red-200 dark:hover:border-red-500/20 transition-all duration-300 select-none overflow-hidden hover:shadow-2xl hover:shadow-red-500/10 dark:hover:shadow-[0_0_40px_-10px_rgba(239,68,68,0.1)]">
               <div className="absolute inset-0 bg-white/[0.01] group-hover:bg-transparent transition-colors"></div>
               <div className="flex flex-col md:flex-row gap-8 items-start md:items-center h-full">
                 <div className="flex-1">
                   <div className="w-14 h-14 bg-red-500/10 rounded-2xl flex items-center justify-center mb-6 text-red-400 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_-5px_rgba(239,68,68,0.2)]">
                     <Brain className="w-7 h-7" />
                   </div>
                   <h3 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">AI Note Taking & Summaries</h3>
                   <p className="text-gray-600 dark:text-foreground/60 leading-relaxed">
                     Get instant AI summaries and generate timestamped notes automatically. Let Wiz capture the key points while you focus on learning.
                   </p>
                 </div>
                 {/* Visual decoration */}
                 <div className="hidden md:flex flex-1 items-center justify-center">
                   <div className="relative w-48 h-48">
                     <div className="absolute inset-0 bg-gradient-to-tr from-red-500 to-orange-500 rounded-full blur-[60px] opacity-20 animate-pulse"></div>
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
            <div className="group relative p-8 rounded-3xl bg-white dark:bg-white/[0.02] border border-gray-200 dark:border-white/[0.08] shadow-lg shadow-gray-200/80 dark:shadow-none hover:border-blue-200 dark:hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden hover:shadow-xl hover:shadow-blue-500/10 dark:hover:shadow-[0_0_30px_-10px_rgba(255,255,255,0.05)]">
               <div className="absolute bottom-0 right-0 w-32 h-32 bg-blue-500/5 rounded-tl-full -mr-8 -mb-8 transition-transform group-hover:scale-110"></div>
               <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 text-blue-500 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_-5px_rgba(59,130,246,0.2)]">
                 <Target className="w-7 h-7" />
               </div>
               <h3 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">Precision Timestamps</h3>
               <p className="text-gray-600 dark:text-foreground/60 leading-relaxed">
                 Every Wiz response and AI note links to the exact second in the video. Click to jump straight to the source context.
               </p>
            </div>

             {/* Feature 4 */}
            <div className="md:col-span-2 group relative p-8 rounded-3xl bg-gradient-to-br from-emerald-50/80 via-white to-white dark:from-emerald-500/5 dark:via-teal-500/5 dark:to-transparent border border-emerald-100 dark:border-white/[0.08] shadow-xl shadow-emerald-100/50 dark:shadow-none hover:border-emerald-200 dark:hover:border-emerald-500/20 transition-all duration-300 select-none overflow-hidden hover:shadow-2xl hover:shadow-emerald-500/10 dark:hover:shadow-[0_0_40px_-10px_rgba(16,185,129,0.1)]">
               <div className="absolute inset-0 bg-white/[0.01] group-hover:bg-transparent transition-colors"></div>
               <div className="flex flex-col md:flex-row gap-8 items-start md:items-center h-full">
                 <div className="flex-1">
                   <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 text-emerald-500 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_-5px_rgba(16,185,129,0.2)]">
                     <Zap className="w-7 h-7" />
                   </div>
                   <h3 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">Unified Knowledge Hub</h3>
                   <p className="text-gray-600 dark:text-foreground/60 leading-relaxed">
                     Your central workspace. Save your Wiz chats, organize your AI notes, and search through your entire video knowledge base.
                   </p>
                 </div>
                 {/* Visual decoration - Matching Feature 2 style but with Emerald theme */}
                 <div className="hidden md:flex flex-1 items-center justify-center">
                   <div className="relative w-48 h-48">
                     <div className="absolute inset-0 bg-gradient-to-tr from-emerald-500 to-teal-500 rounded-full blur-[60px] opacity-20 animate-pulse"></div>
                     <div className="relative z-10 grid grid-cols-2 gap-3 p-4 rounded-2xl bg-black/40 backdrop-blur-xl border border-white/10 -rotate-3 group-hover:rotate-0 transition-transform duration-500">
                        {[1, 2, 3, 4].map((i) => (
                          <div key={i} className="h-12 w-12 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                            <div className="h-6 w-6 rounded bg-emerald-500/20"></div>
                          </div>
                        ))}
                     </div>
                   </div>
                 </div>
               </div>
            </div>

          </div>
        </section>


        {/* HOW IT WORKS */}
        <section id="how-it-works" className="max-w-7xl mx-auto px-6 py-20 select-none">
          
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-4 text-gray-900 dark:text-white">Zero Friction Workflows</h2>
            <p className="text-xl text-gray-500 dark:text-foreground/50">Two powerful ways to master any video.</p>
          </div>

          {/* WORKFLOW 1: WIZ (Chat) */}
          <div className="mb-24">
             <div className="flex items-center gap-3 mb-10 justify-center md:justify-start">
               <div className="p-2.5 bg-violet-100 dark:bg-violet-500/10 rounded-xl border border-violet-200 dark:border-violet-500/10">
                 <Sparkles className="w-5 h-5 text-violet-700 dark:text-violet-400" />
               </div>
               <h3 className="text-2xl font-bold text-violet-950 dark:text-violet-100">Interactive Chat</h3>
             </div>
             
             <div className="grid md:grid-cols-3 gap-8 relative">
                {/* Connecting Line */}
                <div className="hidden md:block absolute top-8 left-[16%] right-[16%] h-0.5 bg-gradient-to-r from-violet-500/0 via-violet-300 dark:via-violet-500/20 to-violet-500/0"></div>
                
                {[
                  { num: '01', title: 'Bring Content', desc: 'Paste a YouTube link or use the extension to initialize Wiz.' },
                  { num: '02', title: 'Ask Anything', desc: 'Challenge Wiz with complex questions about the video content.' },
                  { num: '03', title: 'Deep Understanding', desc: 'Get instant answers with citations linking to exact timestamps.' }
                ].map((step, i) => (
                  <div key={i} className="relative pt-8 group">
                    <div className="w-8 h-8 rounded-full bg-background border-4 border-violet-100 dark:border-violet-500/20 mx-auto absolute top-8 left-1/2 -translate-x-1/2 -translate-y-1/2 md:-translate-y-0 md:top-0 z-10 group-hover:border-violet-300 dark:group-hover:border-violet-500/50 transition-colors shadow-[0_0_15px_-5px_rgba(139,92,246,0.3)]">
                      <div className="w-full h-full rounded-full bg-violet-500 scale-50"></div>
                    </div>
                    <div className="text-center p-6 rounded-2xl bg-white dark:bg-white/[0.01] hover:bg-white dark:hover:bg-white/[0.03] border border-gray-200 dark:border-transparent hover:border-violet-200 dark:hover:border-violet-500/10 transition-all duration-300 group-hover:-translate-y-1 shadow-lg shadow-gray-100/50 dark:shadow-none">
                      <div className="text-4xl font-bold text-violet-500 dark:text-white/10 mb-4 font-mono group-hover:text-violet-600 dark:group-hover:text-violet-500/20 transition-colors">{step.num}</div>
                      <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{step.title}</h3>
                      <p className="text-gray-600 dark:text-foreground/50 text-sm leading-relaxed">{step.desc}</p>
                    </div>
                  </div>
                ))}
             </div>
          </div>

          {/* WORKFLOW 2: NOTES (Capture) */}
          <div>
             <div className="flex items-center gap-3 mb-10 justify-center md:justify-start">
               <div className="p-2.5 bg-red-100 dark:bg-red-500/10 rounded-xl border border-red-200 dark:border-red-500/10">
                 <Brain className="w-5 h-5 text-red-700 dark:text-red-400" />
               </div> 
               <h3 className="text-2xl font-bold text-red-950 dark:text-red-100">Smart Note Taking</h3>
             </div>

             <div className="grid md:grid-cols-3 gap-8 relative">
                {/* Connecting Line */}
                <div className="hidden md:block absolute top-8 left-[16%] right-[16%] h-0.5 bg-gradient-to-r from-red-500/0 via-red-300 dark:via-red-500/20 to-red-500/0"></div>
                
                {[
                  { num: '01', title: 'Start Watching', desc: 'Watch any video on your preffered device browser, mobile app ' },
                  { num: '02', title: 'Auto-Capture', desc: 'Click once to generate AI notes and capture key insights.' },
                  { num: '03', title: 'Build Knowledge', desc: 'Review your notes, search your library, and export anywhere.' }
                ].map((step, i) => (
                  <div key={i} className="relative pt-8 group">
                    <div className="w-8 h-8 rounded-full bg-background border-4 border-red-100 dark:border-red-500/20 mx-auto absolute top-8 left-1/2 -translate-x-1/2 -translate-y-1/2 md:-translate-y-0 md:top-0 z-10 group-hover:border-red-300 dark:group-hover:border-red-500/50 transition-colors shadow-[0_0_15px_-5px_rgba(239,68,68,0.3)]">
                      <div className="w-full h-full rounded-full bg-red-500 scale-50"></div>
                    </div>
                    <div className="text-center p-6 rounded-2xl bg-white dark:bg-white/[0.01] hover:bg-white dark:hover:bg-white/[0.03] border border-gray-200 dark:border-transparent hover:border-red-200 dark:hover:border-red-500/10 transition-all duration-300 group-hover:-translate-y-1 shadow-lg shadow-gray-100/50 dark:shadow-none">
                      <div className="text-4xl font-bold text-red-500 dark:text-white/10 mb-4 font-mono group-hover:text-red-600 dark:group-hover:text-red-500/20 transition-colors">{step.num}</div>
                      <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">{step.title}</h3>
                      <p className="text-gray-600 dark:text-foreground/50 text-sm leading-relaxed">{step.desc}</p>
                    </div>
                  </div>
                ))}
             </div>
          </div>

        </section>


        {/* FINAL CTA */}
        <section className="max-w-5xl mx-auto px-6 py-16">
          <div className="relative rounded-3xl overflow-hidden p-12 md:p-20 text-center select-none group bg-gradient-to-b from-gray-50 to-white dark:bg-white/[0.02] dark:from-transparent dark:to-transparent border border-gray-200 dark:border-white/[0.08] shadow-2xl shadow-gray-200/50 dark:shadow-none hover:border-gray-300 dark:hover:border-white/[0.12] transition-all duration-500">
            
            {/* Ambient background glow - Subtler */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-500/10 rounded-full blur-[120px] pointer-events-none group-hover:bg-red-500/15 transition-colors duration-500"></div>

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
                  className="min-w-[200px] px-8 py-4 bg-white dark:bg-white/[0.05] border border-gray-200 dark:border-white/[0.1] text-foreground hover:bg-gray-50 dark:hover:bg-white/[0.1] hover:border-violet-200 dark:hover:border-white/[0.2] rounded-xl font-bold text-lg transition-all transform hover:-translate-y-1 shadow-xl shadow-gray-200/50 dark:shadow-lg dark:shadow-white/5 inline-flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-5 h-5 text-violet-400" />
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
              
              <div className="flex items-center justify-center gap-2 text-foreground/60 mt-8">
                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
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
