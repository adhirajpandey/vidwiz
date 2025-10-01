import { Clock, Target, Sparkles, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

function LandingPage() {
  return (
    <div>
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
            <Link to="/signup" className="w-64 flex items-center justify-center gap-2 bg-red-500 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-600 transition-all hover:shadow-lg hover:shadow-red-500/25 cursor-pointer">
              Try VidWiz for Free
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a href="#how-it-works" className="w-64 flex items-center justify-center gap-2 bg-background text-foreground/80 px-6 py-2.5 rounded-lg font-medium hover:bg-accent transition-all border border-border hover:border-foreground/30 cursor-pointer">
              How it Works
            </a>
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
          <div className="bg-background rounded-3xl p-12 md:p-16 text-center shadow-2xl">
            <h2 className="text-4xl md:text-5xl font-bold mb-8">
              Ready to Save Hours Every Week?
            </h2>
            <p className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto">
              Join learners, researchers, and professionals who are watching smarter, not longer.
            </p>
            <div className="flex justify-center">
              <Link to="/signup" className="w-64 flex items-center justify-center gap-2 bg-red-500 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-600 transition-all hover:shadow-lg hover:shadow-red-500/25 cursor-pointer">
                Try VidWiz for Free
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
          </div>
        </section>

        
      </main>
    </div>
  );
}

export default LandingPage;
