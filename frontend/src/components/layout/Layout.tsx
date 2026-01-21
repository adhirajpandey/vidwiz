
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import Navbar from './Navbar';
import vidwizLogo from '../../public/vidwiz.png';
import { FaGithub } from 'react-icons/fa';


export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col">
      <Navbar />
      {/* Main content - min-height ensures footer is below fold */}
      <main className="pt-16 min-h-screen">{children}</main>
      
      {/* Footer - same height as navbar */}
      <footer className="h-16 flex items-center bg-background/80 backdrop-blur-md border-t border-border">
        <div className="w-full max-w-screen-2xl mx-auto px-4 md:px-6">
          <div className="flex items-center justify-between">
            {/* Left - Brand */}
            <div className="flex items-center text-sm">
              <Link to="/" className="flex items-center gap-2 text-foreground/60 hover:text-foreground transition-colors">
                <img src={vidwizLogo} alt="VidWiz" className="w-5 h-5" />
                <span className="font-semibold">VidWiz</span>
              </Link>
            </div>

            {/* Right - GitHub */}
            <a 
              href="https://github.com/adhirajpandey/vidwiz" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-foreground/40 hover:text-foreground transition-colors"
            >
              <FaGithub className="w-4 h-4" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
