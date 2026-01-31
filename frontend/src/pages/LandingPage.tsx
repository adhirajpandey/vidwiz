import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { ArrowRight, Sparkles, FileText } from 'lucide-react';
import smartNotesImg from '../public/smart-notes.png';
import wizImg from '../public/wiz.png';
import demoVideo from '../public/vidwiz.mp4';
import { getUserFromToken } from '../lib/authUtils';

export default function LandingPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const userInfo = getUserFromToken();
    setIsLoggedIn(!!userInfo);
  }, []);

  const ctaDestination = isLoggedIn ? '/dashboard' : '/signup';

  return (
    <div className="relative overflow-hidden">
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center">
        {/* Aurora Background Effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {/* Primary aurora - red */}
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-red-500/20 rounded-full blur-[120px] animate-pulse" />
          {/* Secondary aurora - purple */}
          <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-purple-500/15 rounded-full blur-[120px] animate-pulse delay-75" />
          {/* Tertiary aurora - pink */}
          <div className="absolute bottom-1/4 left-1/2 w-96 h-96 bg-pink-500/10 rounded-full blur-[120px] animate-pulse delay-150" />
        </div>

        {/* Content - Two Column Layout */}
        <div className="relative max-w-screen-xl mx-auto px-4 md:px-6 pt-8 pb-20 md:pb-32">
          {/* Badge - Centered Above */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-sm text-foreground/80">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Chat. Note. Master.</span>
            </div>
          </div>

          <div className="grid lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            {/* Left Column - Text & CTAs */}
            <div className="lg:col-span-5 text-center lg:text-left">

              {/* Main Headline */}
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
                <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Talk to the video.
                </span>
                <br />
                <span className="bg-gradient-to-r from-red-400 to-red-500 bg-clip-text text-transparent">
                  Let the notes follow.
                </span>
              </h1>

              {/* Subheadline */}
              <p className="text-base md:text-lg text-foreground/60 mb-10 leading-relaxed max-w-xl mx-auto lg:mx-0">
                The all-in-one companion for video learning. Interrogate the content with our AI Wiz and let the Smart Notes build your personal knowledge vault automatically.
              </p>

              {/* CTA Buttons */}
              <div className="flex flex-col sm:flex-row items-center lg:items-start justify-center lg:justify-start gap-4">
                <Link
                  to={ctaDestination}
                  className="group inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-xl hover:bg-right transition-all duration-500 shadow-2xl shadow-red-500/30 hover:shadow-red-500/50 hover:scale-105"
                >
                  Start Watching Smarter
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link
                  to="/wiz"
                  className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-foreground bg-white/10 backdrop-blur-xl border-2 border-purple-500/30 rounded-xl hover:bg-white/15 hover:border-purple-400/50 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-300"
                >
                  <Sparkles className="w-5 h-5" />
                  Ask Wiz
                </Link>
              </div>
            </div>

            {/* Right Column - Demo Video */}
            <div className="lg:col-span-7 relative">
              {/* Outer glow for video */}
              <div className="absolute -inset-4 bg-gradient-to-r from-red-500/20 via-purple-500/20 to-pink-500/20 rounded-3xl blur-2xl opacity-60" />
              <video
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className="relative w-full h-auto rounded-2xl shadow-2xl ring-1 ring-white/10"
                style={{ imageRendering: 'crisp-edges' }}
              >
                <source src={demoVideo} type="video/mp4" />
                Your browser does not support the video tag.
              </video>
              {/* Ambient glow */}
              <div className="absolute inset-0 bg-gradient-to-t from-red-500/10 to-transparent blur-3xl -z-10" />
            </div>
          </div>
        </div>
      </section>

      {/* Product Showcase Section */}
      <section id="features" className="relative py-32 px-4 md:px-6">
        <div className="max-w-screen-xl mx-auto">
          {/* Section Header */}
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-6xl font-bold mb-6">
              <span className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                Two Ways to Master
              </span>
              <br />
              <span className="bg-gradient-to-r from-red-400 to-purple-400 bg-clip-text text-transparent">
                Video Content
              </span>
            </h2>
            <p className="text-lg text-foreground/60 max-w-2xl mx-auto">
              Whether you need organized notes or conversational insights, VidWiz has you covered.
            </p>
          </div>

          {/* Smart Notes - Left Layout */}
          <div className="grid md:grid-cols-2 gap-12 items-center mb-32">
            {/* Image */}
            <div className="relative group order-2 md:order-1">
              <img
                src={smartNotesImg}
                alt="Smart Notes Interface"
                className="w-full h-auto rounded-2xl shadow-2xl"
              />
              {/* Ambient glow */}
              <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 to-transparent blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10" />
            </div>

            {/* Content */}
            <div className="order-1 md:order-2">
              <div className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-red-500/10 border border-red-500/20 text-base text-red-400 mb-6">
                <FileText className="w-5 h-5" />
                <span className="font-semibold">Smart Notes</span>
              </div>
              <h3 className="text-3xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-white to-white/80 bg-clip-text text-transparent">
                Notes that take themselves.
              </h3>
              <p className="text-lg text-foreground/60 mb-8 leading-relaxed">
                Ditch the "pause-and-type" loop. VidWiz automatically extracts insights and timestamps, keeping you in the flow of learning instead of pausing every 30 seconds.
              </p>
              <ul className="space-y-4">
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-red-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Auto-Extraction:</span>
                    <span className="ml-1">AI captures the core insights.</span>
                  </div>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-red-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Precision Timestamps:</span>
                    <span className="ml-1">Jump to the exact source instantly.</span>
                  </div>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-red-500" />
                  </div>
                  <span>
                    <span className="font-semibold text-foreground/90">Your Knowledge Vault:</span> Search and manage your entire library.
                  </span>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-red-500" />
                  </div>
                  <span>
                    <span className="font-semibold text-foreground/90">Universal Sync:</span> Export to Markdown, PDF, or Notion.
                  </span>
                </li>
              </ul>
            </div>
          </div>

          {/* Wiz - Right Layout */}
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Content */}
            <div>
              <div className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-base text-purple-400 mb-6">
                <Sparkles className="w-5 h-5" />
                <span className="font-semibold">Wiz</span>
              </div>
              <h3 className="text-3xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-white to-white/80 bg-clip-text text-transparent">
                Ask, don't scrub.
              </h3>
              <p className="text-lg text-foreground/60 mb-8 leading-relaxed">
                Skip the search bar. Ask Wiz anything, from high-level concepts to specific details, and get conversational answers tied directly to the video timeline.
              </p>
              <ul className="space-y-4">
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Semantic Search:</span>
                    <span className="ml-1">Ask in plain English, get expert answers.</span>
                  </div>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Context-Aware:</span>
                    <span className="ml-1">Wiz "watches" the video with you.</span>
                  </div>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Deep Jump-Links:</span>
                    <span className="ml-1">Click the answer to play the exact moment.</span>
                  </div>
                </li>
                <li className="flex items-start gap-3 text-foreground/80">
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                  </div>
                  <div>
                    <span className="font-semibold text-foreground/90">Vault Access:</span>
                    <span className="ml-1">Query across your entire video library.</span>
                  </div>
                </li>
              </ul>
            </div>

            {/* Image */}
            <div className="relative group">
              <img
                src={wizImg}
                alt="Wiz AI Assistant Interface"
                className="w-full h-auto rounded-2xl shadow-2xl"
              />
              {/* Ambient glow */}
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-transparent blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10" />
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA Section */}
      <section className="relative py-32 px-4 md:px-6">
        {/* Aurora effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[600px] bg-gradient-to-r from-red-500/20 via-purple-500/20 to-pink-500/20 rounded-full blur-[150px] animate-pulse" />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          {/* Glassmorphic container */}
          <div className="rounded-3xl bg-white/5 backdrop-blur-xl border border-white/10 p-12 md:p-20 shadow-2xl">
            <h2 className="text-4xl md:text-6xl font-bold mb-6">
              <span className="bg-gradient-to-r from-red-400 to-red-500 bg-clip-text text-transparent">
                Let the notes write themselves.
              </span>
              <br />
              <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                Talk to the video.
              </span>
            </h2>
            
            <p className="text-lg text-foreground/60 mb-2 max-w-2xl mx-auto">
              Experience the future of video learning with Smart Notes and Wiz.
            </p>
            <p className="text-lg text-foreground/60 mb-10 max-w-2xl mx-auto font-semibold">
              Start free today.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                to={ctaDestination}
                className="group inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-xl hover:bg-right transition-all duration-500 shadow-2xl shadow-red-500/30 hover:shadow-red-500/50 hover:scale-105"
              >
                Start Watching Smarter
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                to="/wiz"
                className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-foreground bg-white/10 backdrop-blur-xl border-2 border-purple-500/30 rounded-xl hover:bg-white/15 hover:border-purple-400/50 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-300"
              >
                <Sparkles className="w-5 h-5" />
                Ask Wiz
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
