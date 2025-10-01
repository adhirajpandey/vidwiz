import { Clock, Target, Sparkles, ArrowRight, Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import vidwizLogo from './public/vidwiz.png';

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof document !== 'undefined') {
      return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    }
    return 'light';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    try {
      localStorage.setItem('theme', theme);
    } catch {}
  }, [theme]);

  const toggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  return (
    <div className="min-h-screen">
      <nav className="fixed top-0 w-full bg-background/80 backdrop-blur-md border-b border-border z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src={vidwizLogo} alt="VidWiz" className="w-8 h-8" />
            <span className="text-2xl font-bold text-foreground">VidWiz</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-muted-foreground hover:text-foreground transition-colors">Features</a>
            <a href="#how-it-works" className="text-muted-foreground hover:text-foreground transition-colors">How It Works</a>
          </div>
          <div className="flex items-center gap-2">
            <button
              aria-label="Toggle theme"
              onClick={toggleTheme}
              className="h-9 w-9 inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground text-foreground transition-colors"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button className="bg-red-500 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-600 transition-all hover:shadow-lg hover:shadow-red-500/25">
              Get Started
            </button>
          </div>
        </div>
      </nav>

      <main className="pt-12">
        <section className="max-w-7xl mx-auto px-6 py-24 text-center">


          <div className="mb-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-4 py-2 text-sm font-semibold text-gray-800 dark:bg-gray-800 dark:text-gray-300">
              <Sparkles className="h-4 w-4" />
              Now with AI-powered video intelligence
            </div>
          </div>

          <h1 className="text-6xl md:text-7xl font-bold text-foreground mb-8 leading-tight">
            Videos Made <span className="text-red-500">Truly Useful</span>
          </h1>

          <p className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto leading-relaxed">
            Binge less. Learn more.<br />
            YouTube becomes a an organized knowledge hub - take AI notes, review key insights, and jump right to the part you need with VidWiz.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mb-16">
            <button className="bg-red-500 text-white px-8 py-4 rounded-lg font-medium hover:bg-red-600 transition-all hover:shadow-xl hover:shadow-red-500/25 flex items-center gap-2 group">
              Try VidWiz Free
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="bg-background text-foreground/80 px-8 py-4 rounded-lg font-medium hover:bg-accent transition-all border border-border hover:border-foreground/30">
              See how it works
            </button>
          </div>

          
        </section>

        <section id="features" className="max-w-7xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Everything You Need to Save Time
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Powerful features designed to transform how you learn from YouTube
            </p>
          </div>

          <div className="overflow-hidden rounded-2xl border border-border bg-background md:grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x">
            <div className="p-8 transition-all group">
              <div className="w-14 h-14 bg-red-50 dark:bg-red-900/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-red-100 dark:group-hover:bg-red-900/30 transition-colors">
                <Clock className="w-7 h-7 text-red-500" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-3">Time‑Stamped Notes</h3>
              <p className="text-muted-foreground leading-relaxed">
              Never lose track of what matters. Take notes that stick to exact moments in the video, then revisit them instantly. One click, and you’re right back at the part you need.
              </p>
            </div>

            <div className="p-8 transition-all group">
              <div className="w-14 h-14 bg-red-50 dark:bg-red-900/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-red-100 dark:group-hover:bg-red-900/30 transition-colors">
                <Sparkles className="w-7 h-7 text-red-500" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-3">AI‑Generated Notes</h3>
              <p className="text-muted-foreground leading-relaxed">
              Skip the scribbling. Let AI capture concise, accurate notes for any timestamp. Customize, edit, or turn it off whenever you like - your notes, your way.
              </p>
            </div>

            <div className="p-8 transition-all group">
              <div className="w-14 h-14 bg-red-50 dark:bg-red-900/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-red-100 dark:group-hover:bg-red-900/30 transition-colors">
                <Target className="w-7 h-7 text-red-500" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-3">Smart Timestamps</h3>
              <p className="text-muted-foreground leading-relaxed">
              Instantly find what’s relevant and skip the fluff - VidWiz highlights relevant sections so you can jump straight to what matters, no scrubbing required.
              </p>
            </div>
          </div>
        </section>

        <section id="how-it-works" className="bg-background max-w-7xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">Simple. Fast. Powerful.</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">Set up VidWiz - Get started in minutes.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-red-500 text-white rounded-2xl flex items-center justify-center text-2xl font-bold mx-auto mb-6 shadow-lg shadow-red-500/25">1</div>
              <h3 className="text-xl font-bold text-foreground mb-3">Install the Extension</h3>
              <p className="text-muted-foreground">Add VidWiz to your browser to start watching smarter.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-red-500 text-white rounded-2xl flex items-center justify-center text-2xl font-bold mx-auto mb-6 shadow-lg shadow-red-500/25">2</div>
              <h3 className="text-xl font-bold text-foreground mb-3">Set Up Mobile Automation</h3>
              <p className="text-muted-foreground">Sync with your device to take notes on the go.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-red-500 text-white rounded-2xl flex items-center justify-center text-2xl font-bold mx-auto mb-6 shadow-lg shadow-red-500/25">3</div>
              <h3 className="text-xl font-bold text-foreground mb-3">Use the Dashboard</h3>
              <p className="text-muted-foreground">Access everything you need in one place.</p>
            </div>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-6 py-24">
          <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-3xl p-12 md:p-16 text-center text-white shadow-2xl">
            <h2 className="text-4xl md:text-5xl font-bold mb-8">
              Ready to Save Hours Every Week?
            </h2>
            <p className="text-xl text-red-50 mb-12 max-w-2xl mx-auto">
              Join learners, researchers, and professionals who are watching smarter, not longer.
            </p>
            <button className="bg-white text-red-500 px-8 py-4 rounded-lg font-medium hover:bg-gray-50 transition-all shadow-xl hover:shadow-2xl flex items-center gap-2 mx-auto group">
              Get Started Free
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </section>

        
      </main>

      <footer className="bg-background border-t border-border py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <img src={vidwizLogo} alt="VidWiz" className="w-6 h-6" />
              <span className="text-xl font-bold text-foreground">VidWiz</span>
            </div>
            <p className="text-muted-foreground text-sm">© 2025 VidWiz. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
