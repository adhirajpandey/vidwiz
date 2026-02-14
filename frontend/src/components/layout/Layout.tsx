
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Navbar from './Navbar';
import vidwizLogo from '../../public/vidwiz.png';
import { FaGithub } from 'react-icons/fa';


export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const isLandingPage = location.pathname === '/';

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground">
      {!isLandingPage && <Navbar />}
      {/* Main content - min-height ensures footer is below fold */}
      <main className={!isLandingPage ? "pt-16 min-h-screen" : "min-h-screen"}>{children}</main>
      
      {(
        /* Footer */
        <footer className="py-3 md:py-4 bg-background/80 backdrop-blur-md border-t border-border">
          <div className="w-full max-w-screen-2xl mx-auto px-4 md:px-6">
            {/* Mobile: single row */}
            <div className="relative flex md:hidden items-center justify-between text-sm">
              <Link to="/" className="flex items-center gap-2 text-foreground/50 hover:text-foreground transition-colors">
                <img src={vidwizLogo} alt="VidWiz" className="w-4 h-4" />
                <span className="font-semibold">VidWiz</span>
              </Link>
              <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-4">
                <Link to="/help" className="text-foreground/40 hover:text-foreground/80 transition-colors">Help</Link>
                <Link to="/privacy" className="text-foreground/40 hover:text-foreground/80 transition-colors">Privacy</Link>
              </div>
              <a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer" className="text-foreground/40 hover:text-foreground transition-colors">
                <FaGithub className="w-4 h-4" />
              </a>
            </div>

            {/* Desktop: two rows */}
            <div className="hidden md:block space-y-3">
              <div className="flex items-center justify-center gap-6 text-sm">
                <Link to="/help" className="text-foreground/40 hover:text-foreground/80 transition-colors">Help</Link>
                <Link to="/privacy" className="text-foreground/40 hover:text-foreground/80 transition-colors">Privacy</Link>
              </div>
              <div className="relative flex items-center justify-between">
                <Link to="/" className="flex items-center gap-2 text-foreground/50 hover:text-foreground transition-colors text-sm">
                  <img src={vidwizLogo} alt="VidWiz" className="w-4 h-4" />
                  <span className="font-semibold">VidWiz</span>
                </Link>
                <p className="absolute left-1/2 -translate-x-1/2 text-foreground/30 text-xs">© {new Date().getFullYear()} VidWiz. All rights reserved.</p>
                <a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm text-foreground/40 hover:text-foreground transition-colors">
                  <FaGithub className="w-4 h-4" />
                  <span>GitHub</span>
                </a>
              </div>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}
