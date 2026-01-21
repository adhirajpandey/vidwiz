
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import Navbar from './Navbar';
import vidwizLogo from '../../public/vidwiz.png';
import { FaGithub, FaHeart } from 'react-icons/fa';


export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="pt-16 flex-grow">{children}</main>
      
      {/* Premium Footer */}
      <footer className="relative bg-background border-t border-white/[0.06] select-none overflow-hidden">
        {/* Subtle ambient glow */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-red-500/20 to-transparent"></div>
        <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-red-500/[0.02] to-transparent pointer-events-none"></div>
        
        <div className="relative max-w-screen-2xl mx-auto px-4 md:px-6 py-10 md:py-14">
          {/* Main Footer Content */}
          <div className="flex flex-col gap-8">
            {/* Top Section */}
            <div className="flex flex-col md:flex-row items-center md:items-start justify-between gap-8">
              {/* Brand Section */}
              <div className="flex flex-col items-center md:items-start gap-4">
                <Link to="/" className="group flex items-center gap-3">
                  <div className="relative">
                    <div className="absolute inset-0 bg-red-500/20 rounded-xl blur-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                    <img src={vidwizLogo} alt="VidWiz" className="relative w-10 h-10 transition-transform duration-300 group-hover:scale-105" />
                  </div>
                  <span className="text-2xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                    VidWiz
                  </span>
                </Link>
                <p className="text-foreground/40 text-sm text-center md:text-left max-w-xs">
                  Transform how you learn from YouTube videos with AI-powered notes and smart timestamps.
                </p>
              </div>

              {/* Links Section */}
              <div className="flex flex-wrap justify-center md:justify-end gap-x-8 gap-y-4">
                <div className="flex flex-col items-center md:items-start gap-3">
                  <span className="text-xs font-semibold text-foreground/30 uppercase tracking-wider">Product</span>
                  <Link to="/dashboard" className="text-sm text-foreground/60 hover:text-foreground transition-colors">Dashboard</Link>
                  <a href="#features" className="text-sm text-foreground/60 hover:text-foreground transition-colors">Features</a>
                </div>
                <div className="flex flex-col items-center md:items-start gap-3">
                  <span className="text-xs font-semibold text-foreground/30 uppercase tracking-wider">Account</span>
                  <Link to="/login" className="text-sm text-foreground/60 hover:text-foreground transition-colors">Sign In</Link>
                  <Link to="/signup" className="text-sm text-foreground/60 hover:text-foreground transition-colors">Get Started</Link>
                </div>
              </div>
            </div>

            {/* Divider */}
            <div className="h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent"></div>

            {/* Bottom Section */}
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              {/* Copyright */}
              <div className="flex items-center gap-2 text-sm text-foreground/40">
                <span>© 2025 VidWiz.</span>
                <span className="hidden sm:inline">All rights reserved.</span>
              </div>

                {/* Social-like icons */}
                <div className="flex items-center gap-2">
                  <a
                    href="https://github.com/adhirajpandey/vidwiz"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] hover:border-white/[0.12] text-xs font-medium text-foreground/60 hover:text-foreground transition-all duration-200 group"
                  >
                    <FaGithub className="w-3.5 h-3.5" />
                    <span>Star on GitHub</span>
                    <FaHeart className="w-3 h-3 text-red-500/50 group-hover:text-red-500 transition-colors" />
                  </a>
                </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
