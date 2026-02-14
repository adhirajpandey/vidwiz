
import { Link } from 'react-router-dom';
import { Sparkles, Download, LogIn, Settings, PenLine, MessageCircle, ArrowRight, Chrome, FileText, Bot } from 'lucide-react';
import config from '../config';

export default function HelpPage() {
  return (
    <div className="relative overflow-hidden min-h-screen bg-background text-foreground">
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-red-500/10 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[120px] animate-pulse delay-75" />
        <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-pink-500/10 rounded-full blur-[120px] animate-pulse delay-150" />
      </div>

      <div className="relative max-w-4xl mx-auto px-4 md:px-6 py-12 md:py-20">
        {/* Header */}
        <div className="text-center mb-10 md:mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-sm text-foreground/80 mb-6">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span>Getting Started</span>
          </div>
          <h1 className="text-3xl md:text-5xl font-bold mb-4 md:mb-6">
            <span className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
              Set Up VidWiz in
            </span>{' '}
            <span className="bg-gradient-to-r from-red-400 to-purple-400 bg-clip-text text-transparent">
              Minutes
            </span>
          </h1>
          <p className="text-base md:text-lg text-foreground/60 max-w-2xl mx-auto">
            Follow these simple steps to start taking smarter notes and chatting with any YouTube video.
          </p>
        </div>

        {/* Setup Steps */}
        <div className="space-y-5 md:space-y-8">

          {/* Step 1: Install Extension */}
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10 hover:border-white/20 transition-colors">
            <div className="flex items-start gap-3 md:gap-5">
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-red-500/20">
                1
              </div>
              <div className="flex-1">
                <h2 className="text-lg md:text-2xl font-bold mb-2 md:mb-3 text-white flex items-center gap-2">
                  <Download className="w-5 h-5 text-red-400" />
                  Install the Chrome Extension
                </h2>
                <p className="text-foreground/80 leading-relaxed mb-4">
                  VidWiz works as a Chrome extension that sits right inside your YouTube player. Install it from the Chrome Web Store to get started.
                </p>
                <a
                  href={config.CHROME_WEBSTORE_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-600 to-red-500 rounded-xl hover:shadow-lg hover:shadow-red-500/30 hover:scale-[1.02] transition-all duration-300"
                >
                  <Chrome className="w-4 h-4" />
                  Install Chrome Extension
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
                <p className="text-foreground/50 text-sm mt-3">
                  After installing, pin the VidWiz icon to your Chrome toolbar for quick access.
                </p>
              </div>
            </div>
          </section>

          {/* Step 2: Create Account & Login */}
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10 hover:border-white/20 transition-colors">
            <div className="flex items-start gap-3 md:gap-5">
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-purple-500/20">
                2
              </div>
              <div className="flex-1">
                <h2 className="text-lg md:text-2xl font-bold mb-2 md:mb-3 text-white flex items-center gap-2">
                  <LogIn className="w-5 h-5 text-purple-400" />
                  Create Your Account
                </h2>
                <p className="text-foreground/80 leading-relaxed mb-4">
                  Sign up with Google to create your VidWiz account. You'll get <strong className="text-white">{config.SIGNUP_CREDITS} free credits</strong> on signup to explore Smart Notes and Wiz.
                </p>
                <Link
                  to="/signup"
                  className="group inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-pink-500 rounded-xl hover:shadow-lg hover:shadow-purple-500/30 hover:scale-[1.02] transition-all duration-300"
                >
                  Create Account
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <p className="text-foreground/50 text-sm mt-3">
                  Already have an account? <Link to="/login" className="text-purple-400 hover:text-purple-300 transition-colors">Log in here</Link>.
                </p>
              </div>
            </div>
          </section>

          {/* Step 3: Enable AI Notes */}
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10 hover:border-white/20 transition-colors">
            <div className="flex items-start gap-3 md:gap-5">
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-pink-500 to-pink-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-pink-500/20">
                3
              </div>
              <div className="flex-1">
                <h2 className="text-lg md:text-2xl font-bold mb-2 md:mb-3 text-white flex items-center gap-2">
                  <Settings className="w-5 h-5 text-pink-400" />
                  Enable AI Smart Notes
                </h2>
                <p className="text-foreground/80 leading-relaxed mb-4">
                  Head to your profile page and toggle on <strong className="text-white">AI Smart Notes</strong>. This allows VidWiz to automatically generate intelligent, timestamped notes while you watch any YouTube video.
                </p>
                <Link
                  to="/profile"
                  className="group inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-foreground bg-white/10 border border-white/10 rounded-xl hover:bg-white/15 hover:border-white/20 transition-all duration-300"
                >
                  Go to Profile
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <p className="text-foreground/50 text-sm mt-3">
                  Each AI Smart Note costs 1 credit. Manual notes are always free and unlimited.
                </p>
              </div>
            </div>
          </section>

          {/* Step 4: Take Notes */}
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10 hover:border-white/20 transition-colors">
            <div className="flex items-start gap-3 md:gap-5">
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-green-500/20">
                4
              </div>
              <div className="flex-1">
                <h2 className="text-lg md:text-2xl font-bold mb-2 md:mb-3 text-white flex items-center gap-2">
                  <PenLine className="w-5 h-5 text-green-400" />
                  Start Taking Smart Notes
                </h2>
                <p className="text-foreground/80 leading-relaxed mb-4">
                  Open any YouTube video and click the VidWiz extension icon in your toolbar. A panel will appear where you can:
                </p>
                <ul className="space-y-3 mb-4">
                  <li className="flex items-start gap-3 text-foreground/80">
                    <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <FileText className="w-3.5 h-3.5 text-green-400" />
                    </div>
                    <span><strong className="text-white">Manual Notes</strong>: Type your own note and save it at the current timestamp. Free and unlimited.</span>
                  </li>
                  <li className="flex items-start gap-3 text-foreground/80">
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    </div>
                    <span><strong className="text-white">AI Smart Notes</strong>: Leave the note text empty and hit save. VidWiz will use AI to automatically generate a note for that timestamp. Costs 1 credit per note.</span>
                  </li>
                </ul>
                <p className="text-foreground/50 text-sm">
                  All your notes are saved automatically and synced to your <Link to="/dashboard" className="text-purple-400 hover:text-purple-300 transition-colors">Dashboard</Link> where you can review, edit, and export them.
                </p>
              </div>
            </div>
          </section>

          {/* Step 5: Chat with Wiz */}
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10 hover:border-white/20 transition-colors">
            <div className="flex items-start gap-3 md:gap-5">
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-blue-500/20">
                5
              </div>
              <div className="flex-1">
                <h2 className="text-lg md:text-2xl font-bold mb-2 md:mb-3 text-white flex items-center gap-2">
                  <MessageCircle className="w-5 h-5 text-blue-400" />
                  Chat with Wiz
                </h2>
                <p className="text-foreground/80 leading-relaxed mb-4">
                  Have questions about a video? Open it in <strong className="text-white">Wiz</strong> to chat with AI. You can open Wiz in two ways:
                </p>
                <ul className="space-y-3 mb-4">
                  <li className="flex items-start gap-3 text-foreground/80">
                    <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Chrome className="w-3.5 h-3.5 text-blue-400" />
                    </div>
                    <span><strong className="text-white">From the extension</strong>: Click the "Open in Wiz" button while watching any YouTube video.</span>
                  </li>
                  <li className="flex items-start gap-3 text-foreground/80">
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Bot className="w-3.5 h-3.5 text-purple-400" />
                    </div>
                    <span><strong className="text-white">From the web</strong>: Go to <Link to="/wiz" className="text-purple-400 hover:text-purple-300 transition-colors">Wiz</Link> and paste any YouTube video link.</span>
                  </li>
                </ul>
                <Link
                  to="/wiz"
                  className="group inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-500 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 hover:scale-[1.02] transition-all duration-300"
                >
                  <Bot className="w-4 h-4" />
                  Try Wiz
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <p className="text-foreground/50 text-sm mt-3">
                  Each Wiz conversation costs 5 credits per video. Paste any YouTube link to get started.
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Credits Info */}
        <div className="mt-8 md:mt-12 bg-white/5 backdrop-blur-md rounded-2xl p-5 md:p-8 border border-white/10">
          <h2 className="text-xl font-bold mb-4 text-white text-center">Understanding Credits</h2>
          <div className="grid sm:grid-cols-3 gap-6 text-center">
            <div className="p-4">
              <div className="text-2xl md:text-3xl font-bold text-green-400 mb-1">Free</div>
              <p className="text-foreground/60 text-sm">Manual video notes</p>
            </div>
            <div className="p-4">
              <div className="text-2xl md:text-3xl font-bold text-red-400 mb-1">1 credit</div>
              <p className="text-foreground/60 text-sm">Per AI Smart Note</p>
            </div>
            <div className="p-4">
              <div className="text-2xl md:text-3xl font-bold text-purple-400 mb-1">5 credits</div>
              <p className="text-foreground/60 text-sm">Per Wiz conversation</p>
            </div>
          </div>
          <p className="text-center text-foreground/50 text-sm mt-4">
            Need more credits? <Link to="/profile" className="text-purple-400 hover:text-purple-300 transition-colors">Buy credits from your profile</Link>. No subscriptions required.
          </p>
        </div>
      </div>
    </div>
  );
}
