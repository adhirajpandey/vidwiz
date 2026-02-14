import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { ArrowRight, Sparkles, FileText } from 'lucide-react';
import smartNotesImg from '../public/smart-notes.png';
import wizImg from '../public/wiz.png';
import demoVideo from '../public/vidwiz.mp4';
import { getUserFromToken } from '../lib/authUtils';
import config from '../config';

export default function LandingPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    // Force dark mode on landing page
    document.documentElement.classList.add('dark');
    
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
        <div className="relative max-w-screen-xl mx-auto px-4 md:px-6 pt-8 pb-12 md:pb-20">
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

          {/* Chrome Web Store Button - Centered below grid */}
          <div className="flex justify-center mt-24">
            <a
              href={config.CHROME_WEBSTORE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-center gap-2.5 px-5 py-2.5 text-sm font-medium text-foreground/70 bg-white/5 backdrop-blur-xl border border-white/10 rounded-xl hover:bg-white/10 hover:border-white/20 hover:text-foreground/90 hover:shadow-lg hover:shadow-white/5 transition-all duration-300"
            >
              {/* Chrome Web Store Icon */}
              <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 192 192" xmlns="http://www.w3.org/2000/svg">
                <path d="M58 24c-8 0-14 6-14 14v4H28c-3 0-5 2-5 5l-7 90c0 3 1 5 3 7s5 3 7 3h140c3 0 5-1 7-3s3-4 3-7l-7-90c0-3-2-5-5-5h-16v-4c0-8-6-14-14-14H58z" fill="#4285F4"/>
                <path d="M96 88a36 36 0 100 72 36 36 0 000-72z" fill="white"/>
                <path d="M96 96a28 28 0 00-24 14l14 8a14 14 0 0124 0l14-8a28 28 0 00-28-14z" fill="#EA4335"/>
                <path d="M72 110a28 28 0 000 28l14-8a14 14 0 010-12l-14-8z" fill="#4285F4"/>
                <path d="M96 152a28 28 0 0024-14l-14-8a14 14 0 01-24 0l-14 8a28 28 0 0028 14z" fill="#34A853"/>
                <path d="M120 138a28 28 0 000-28l-14 8a14 14 0 010 12l14 8z" fill="#FBBC05"/>
                <circle cx="96" cy="124" r="8" fill="#4285F4"/>
              </svg>
              <span>Install Chrome Extension</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>
          <div className="flex justify-center mt-3">
            <Link to="/help" className="inline-flex items-center gap-1 text-sm text-purple-400 hover:text-purple-300 transition-colors">
              See how it works <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Product Showcase Section */}
      <section id="features" className="relative py-12 md:py-20 px-4 md:px-6">
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
          <div className="grid md:grid-cols-2 gap-12 items-center mb-12 md:mb-20">
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

      {/* Pricing Section */}
      <section id="pricing" className="relative py-12 md:py-20 px-4 md:px-6">
        {/* Background effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[120px] animate-pulse" />
          <div className="absolute bottom-1/3 right-1/4 w-96 h-96 bg-red-500/10 rounded-full blur-[120px] animate-pulse delay-75" />
        </div>

        <div className="relative max-w-screen-xl mx-auto">
          {/* Section Header */}
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-6xl font-bold mb-6">
              <span className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                Simple,
              </span>{' '}
              <span className="bg-gradient-to-r from-red-400 to-purple-400 bg-clip-text text-transparent">
                Credit-Based Pricing
              </span>
            </h2>
            <p className="text-lg text-foreground/60 max-w-2xl mx-auto">
              Start free. Buy credits when you need more. No subscriptions, no commitments.
            </p>
            <Link to="/help" className="inline-flex items-center gap-1 text-sm text-purple-400 hover:text-purple-300 transition-colors mt-3">
              See how it works <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Pricing Cards */}
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            
            {/* Free Tier */}
            <div className="rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 p-8 flex flex-col hover:border-white/20 transition-all duration-300">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-foreground/90 mb-2">Free</h3>
                <p className="text-foreground/50 text-sm">Get started with VidWiz</p>
              </div>
              <div className="mb-8">
                <span className="text-5xl font-bold text-foreground">₹0</span>
                <span className="text-foreground/50 ml-2">forever</span>
              </div>
              <ul className="space-y-3 mb-10 flex-1">
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>{config.SIGNUP_CREDITS} credits on signup</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Unlimited video notes</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Limited Smart Notes & Wiz</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Chrome extension</span>
                </li>
              </ul>
              <Link
                to="/signup"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 text-sm font-semibold text-foreground bg-white/10 border border-white/10 rounded-xl hover:bg-white/15 hover:border-white/20 transition-all duration-300"
              >
                Get Started Free
              </Link>
            </div>

            {/* 600 Credits Tier - Highlighted */}
            <div className="relative rounded-2xl bg-white/5 backdrop-blur-xl border border-purple-500/30 p-8 flex flex-col hover:border-purple-400/50 transition-all duration-300 shadow-lg shadow-purple-500/10">
              {/* Popular badge */}
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                <span className="inline-flex items-center gap-1.5 px-4 py-1 text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-pink-500 rounded-full uppercase tracking-wider">
                  <Sparkles className="w-3 h-3" />
                  Most Popular
                </span>
              </div>
              <div className="mb-6">
                <h3 className="text-xl font-bold text-foreground/90 mb-2">{config.PRICING[1].credits} Credits</h3>
                <p className="text-foreground/50 text-sm">For regular learners</p>
              </div>
              <div className="mb-8">
                <span className="text-5xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">₹{config.PRICING[1].price}</span>
                <span className="text-foreground/50 ml-2">one-time</span>
              </div>
              <ul className="space-y-3 mb-10 flex-1">
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>{config.PRICING[1].credits} credits</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Everything in Free</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>₹{config.PRICING[1].perCredit} per credit</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Credits never expire</span>
                </li>
              </ul>
              <Link
                to="/profile"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-pink-500 rounded-xl hover:shadow-lg hover:shadow-purple-500/30 hover:scale-[1.02] transition-all duration-300"
              >
                Buy Credits
              </Link>
            </div>

            {/* 1500 Credits Tier */}
            <div className="rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 p-8 flex flex-col hover:border-white/20 transition-all duration-300">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-foreground/90 mb-2">{config.PRICING[2].credits} Credits</h3>
                <p className="text-foreground/50 text-sm">For power users</p>
              </div>
              <div className="mb-8">
                <span className="text-5xl font-bold text-foreground">₹{config.PRICING[2].price}</span>
                <span className="text-foreground/50 ml-2">one-time</span>
              </div>
              <ul className="space-y-3 mb-10 flex-1">
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>{config.PRICING[2].credits} credits</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Everything in Free</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>₹{config.PRICING[2].perCredit} per credit (best value)</span>
                </li>
                <li className="flex items-center gap-2.5 text-foreground/70 text-sm">
                  <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span>Credits never expire</span>
                </li>
              </ul>
              <Link
                to="/profile"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-red-600 to-red-500 rounded-xl hover:shadow-lg hover:shadow-red-500/30 hover:scale-[1.02] transition-all duration-300"
              >
                Buy Credits
              </Link>
            </div>
          </div>

          {/* Bottom note */}
          <p className="text-center text-foreground/40 text-sm mt-10">
            1 credit = 1 Smart Note. 5 credits = 1 Wiz conversation. No subscriptions, buy only what you need.
          </p>
        </div>
      </section>

      {/* Final CTA Section */}
      <section className="relative py-12 md:py-20 px-4 md:px-6">
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

              {/* Chrome Web Store Button */}
              <div className="flex justify-center mt-10">
                <a
                  href={config.CHROME_WEBSTORE_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-2.5 px-5 py-2.5 text-sm font-medium text-foreground/70 bg-white/5 backdrop-blur-xl border border-white/10 rounded-xl hover:bg-white/10 hover:border-white/20 hover:text-foreground/90 hover:shadow-lg hover:shadow-white/5 transition-all duration-300"
                >
                  {/* Chrome Web Store Icon */}
                  <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 192 192" xmlns="http://www.w3.org/2000/svg">
                    <path d="M58 24c-8 0-14 6-14 14v4H28c-3 0-5 2-5 5l-7 90c0 3 1 5 3 7s5 3 7 3h140c3 0 5-1 7-3s3-4 3-7l-7-90c0-3-2-5-5-5h-16v-4c0-8-6-14-14-14H58z" fill="#4285F4"/>
                    <path d="M96 88a36 36 0 100 72 36 36 0 000-72z" fill="white"/>
                    <path d="M96 96a28 28 0 00-24 14l14 8a14 14 0 0124 0l14-8a28 28 0 00-28-14z" fill="#EA4335"/>
                    <path d="M72 110a28 28 0 000 28l14-8a14 14 0 010-12l-14-8z" fill="#4285F4"/>
                    <path d="M96 152a28 28 0 0024-14l-14-8a14 14 0 01-24 0l-14 8a28 28 0 0028 14z" fill="#34A853"/>
                    <path d="M120 138a28 28 0 000-28l-14 8a14 14 0 010 12l14 8z" fill="#FBBC05"/>
                    <circle cx="96" cy="124" r="8" fill="#4285F4"/>
                  </svg>
                  <span>Install Chrome Extension</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </a>
              </div>
              <div className="flex justify-center mt-3">
                <Link to="/help" className="inline-flex items-center gap-1 text-sm text-purple-400 hover:text-purple-300 transition-colors">
                  See how it works <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
          </div>
        </div>
      </section>
    </div>
  );
}
