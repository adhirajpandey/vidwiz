
import { useEffect, useState } from 'react';
import { Clock, Target, Sparkles, ArrowRight, Play, CheckCircle2, Zap, Brain, ChevronRight, LayoutDashboard } from 'lucide-react';
import { Link } from 'react-router-dom';
import AmbientBackground from '../components/ui/AmbientBackground';
import GradientText from '../components/ui/GradientText';
import GlassCard from '../components/ui/GlassCard';

function LandingPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsLoggedIn(!!token);
  }, []);

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

            {/* Github Star Badge */}


            {/* Headline */}
            <h1 className="max-w-4xl text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-8 leading-[1.1] animate-in fade-in slide-in-from-bottom-8 duration-1000 select-none">
              Video learning, <br />
              <GradientText>
                truly unlocked.
              </GradientText>
            </h1>

            {/* Subheadline */}
            <p className="max-w-2xl text-lg md:text-xl text-foreground/60 mb-12 leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-200 select-none">
              Transform passive watching into active learning. VidWiz extracts key insights, 
              generates smart notes, and helps you master content 10x faster.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center gap-4 mb-10 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
              <Link 
                to={isLoggedIn ? "/dashboard" : "/signup"} 
                className="w-full sm:w-auto min-w-[180px] inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-red-600 to-red-500 rounded-xl hover:scale-105 active:scale-95 transition-all duration-300 shadow-[0_0_40px_-10px_rgba(239,68,68,0.4)] hover:shadow-[0_0_60px_-15px_rgba(239,68,68,0.6)]"
              >
                {isLoggedIn ? (
                  <>
                    <LayoutDashboard className="w-5 h-5" />
                    Open Dashboard
                  </>
                ) : (
                  <>
                    Start for Free
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </Link>
              
              <a 
                href="#how-it-works" 
                className="w-full sm:w-auto min-w-[180px] inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-medium text-foreground/80 bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.15] rounded-xl transition-all duration-300"
              >
                How it Works
              </a>
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

            {/* Mock UI Showcase */}
            <div className="relative w-full max-w-5xl mx-auto animate-in fade-in zoom-in-95 duration-1000 delay-500">
              {/* Glow behind mock */}
              <div className="absolute -inset-1 bg-gradient-to-r from-red-500/20 via-violet-500/20 to-blue-500/20 rounded-3xl blur-xl opacity-50"></div>
              
              <GlassCard className="relative rounded-2xl md:rounded-3xl p-2 overflow-hidden select-none bg-black/60 border-white/10">
                {/* Window Controls */}
                <div className="absolute top-0 left-0 right-0 h-10 bg-white/[0.03] border-b border-white/[0.05] flex items-center px-4 gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500/20"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500/20"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500/20"></div>
                </div>

                {/* Content Area */}
                <div className="mt-10 grid grid-cols-12 gap-1 md:gap-2 h-[300px] md:h-[500px] bg-black/40">
                  {/* Video Player Area */}
                  <div className="col-span-12 md:col-span-8 bg-white/[0.02] flex items-center justify-center relative group overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-black/0 to-black/60"></div>
                    <div className="w-16 h-16 md:w-20 md:h-20 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-2xl group-hover:scale-110 transition-transform duration-500">
                      <Play className="w-6 h-6 md:w-8 md:h-8 text-white fill-white ml-1" />
                    </div>
                    
                    {/* Floating timestamp badges using absolute positioning to simulate interface */}
                    <div className="absolute bottom-6 left-6 flex gap-2">
                      <div className="px-3 py-1 rounded-lg bg-black/60 backdrop-blur-md text-xs font-medium text-white/90 border border-white/10">
                        12:45 / 24:10
                      </div>
                    </div>
                  </div>

                  {/* Notes Sidebar Area */}
                  <div className="col-span-12 md:col-span-4 bg-white/[0.04] border-l border-white/[0.05] p-4 md:p-6 flex flex-col gap-4">
                    <div className="h-6 w-32 bg-white/10 rounded animate-pulse"></div>
                    <div className="h-px w-full bg-white/[0.05] my-2"></div>
                    
                    {/* Simulated Note Card */}
                    <div className="p-3 md:p-4 rounded-xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20">
                      <div className="flex gap-2 mb-2">
                        <div className="w-4 h-4 rounded bg-violet-500/40"></div>
                        <div className="h-4 w-20 bg-violet-500/20 rounded"></div>
                      </div>
                      <div className="space-y-2">
                        <div className="h-3 w-full bg-white/10 rounded"></div>
                        <div className="h-3 w-[90%] bg-white/10 rounded"></div>
                        <div className="h-3 w-[40%] bg-white/10 rounded"></div>
                      </div>
                    </div>

                    {/* Simulated User Note */}
                    <div className="p-3 md:p-4 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                      <div className="flex gap-2 mb-2">
                        <div className="w-4 h-4 rounded bg-emerald-500/40"></div>
                        <div className="h-4 w-16 bg-emerald-500/20 rounded"></div>
                      </div>
                      <div className="space-y-2">
                        <div className="h-3 w-full bg-white/5 rounded"></div>
                        <div className="h-3 w-[75%] bg-white/5 rounded"></div>
                      </div>
                    </div>
                  </div>
              </div>
            </GlassCard>
           </div>
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
                 <Clock className="w-7 h-7" />
               </div>
               <h3 className="text-2xl font-bold mb-3">Precision Timestamps</h3>
               <p className="text-foreground/60 leading-relaxed">
                 Notes are linked to the exact second. Click any note to jump instantly to that moment in the video.
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
                   <h3 className="text-2xl font-bold mb-3">AI Intelligence Layer</h3>
                   <p className="text-foreground/60 leading-relaxed mb-6">
                     Our AI analyzes video context to generate summary notes automatically. It understands technical tutorials, lectures, and long-form content instantly.
                   </p>
                   <div className="flex gap-2">
                     <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 text-violet-300 text-xs font-medium">GPT-4 Powered</span>
                     <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-fuchsia-500/10 text-fuchsia-300 text-xs font-medium">Auto-Summary</span>
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
               <h3 className="text-2xl font-bold mb-3">Focus Mode</h3>
               <p className="text-foreground/60 leading-relaxed">
                 Eliminate distractions. Our organized dashboard keeps you focused on learning, not the algorithm's next recommendation.
               </p>
            </div>

             {/* Feature 4 */}
            <div className="md:col-span-2 group relative p-8 rounded-3xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300 select-none overflow-hidden">
               <div className="flex flex-col md:flex-row gap-8 items-center h-full">
                 <div className="flex-1">
                   <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 text-emerald-500 group-hover:scale-110 transition-transform duration-300">
                     <Zap className="w-7 h-7" />
                   </div>
                   <h3 className="text-2xl font-bold mb-3">Lightning Fast Sync</h3>
                   <p className="text-foreground/60 leading-relaxed">
                     Your notes sync instantly across devices. Start on desktop, review on mobile. 
                     Works seamlessly with our browser extension to capture content as you watch.
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
              { num: '01', title: 'Install Extension', desc: 'Add to Chrome in seconds. It sits quietly until you need it.' },
              { num: '02', title: 'Watch & Click', desc: 'Click the VidWiz button on any video to capture timestamped notes instantly.' },
              { num: '03', title: 'Review & Master', desc: 'Access your curated knowledge hub in the dashboard anytime.' }
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
                <div className="flex items-center gap-2 text-foreground/60 px-6 py-4">
                  <CheckCircle2 className="w-5 h-5 text-red-500" />
                  <span className="text-sm font-medium">No credit card required</span>
                </div>
              </div>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}

export default LandingPage;
