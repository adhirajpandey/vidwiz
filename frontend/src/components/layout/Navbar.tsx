import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun, LogOut, LayoutDashboard, User } from 'lucide-react';
import vidwizLogo from '../../public/vidwiz.png';

export default function Navbar() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof document !== 'undefined') {
      return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    }
    return 'light';
  });
  const location = useLocation();
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsLoggedIn(!!token);
  }, [location]);

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

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
    navigate('/login');
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="fixed top-0 w-full z-50 select-none">
      {/* Subtle gradient background with glassmorphism */}
      <div className="absolute inset-0 bg-background/70 backdrop-blur-xl border-b border-white/[0.06]"></div>
      
      {/* Ambient top glow */}
      <div className="absolute inset-x-0 -top-20 h-20 bg-gradient-to-b from-red-500/5 to-transparent pointer-events-none"></div>
      
      <div className="relative max-w-7xl mx-auto px-4 md:px-6 py-3 md:py-4 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="group flex items-center gap-2.5">
          <div className="relative">
            <div className="absolute inset-0 bg-red-500/20 rounded-lg blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <img src={vidwizLogo} alt="VidWiz" className="relative w-8 h-8 md:w-9 md:h-9 transition-transform duration-300 group-hover:scale-105" />
          </div>
          <span className="text-xl md:text-2xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            VidWiz
          </span>
        </Link>

        {/* Navigation Links */}
        <div className="hidden md:flex items-center gap-1">
          {isLoggedIn ? (
            <>
              <Link 
                to="/dashboard" 
                className={`group inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive('/dashboard') 
                    ? 'bg-white/[0.08] text-foreground' 
                    : 'text-foreground/60 hover:text-foreground hover:bg-white/[0.04]'
                }`}
              >
                <LayoutDashboard className={`w-4 h-4 transition-colors ${isActive('/dashboard') ? 'text-red-400' : 'group-hover:text-red-400'}`} />
                Dashboard
              </Link>
              <Link 
                to="/profile" 
                className={`group inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive('/profile') 
                    ? 'bg-white/[0.08] text-foreground' 
                    : 'text-foreground/60 hover:text-foreground hover:bg-white/[0.04]'
                }`}
              >
                <User className={`w-4 h-4 transition-colors ${isActive('/profile') ? 'text-red-400' : 'group-hover:text-red-400'}`} />
                Profile
              </Link>
            </>
          ) : (
            location.pathname === '/' && (
              <>
                <a 
                  href="#features" 
                  className="px-4 py-2 rounded-lg text-sm font-medium text-foreground/60 hover:text-foreground hover:bg-white/[0.04] transition-all duration-200"
                >
                  Features
                </a>
                <a 
                  href="#how-it-works" 
                  className="px-4 py-2 rounded-lg text-sm font-medium text-foreground/60 hover:text-foreground hover:bg-white/[0.04] transition-all duration-200"
                >
                  How It Works
                </a>
              </>
            )
          )}
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2 md:gap-3">
          {/* GitHub Star Button - Hidden on mobile, visible on desktop */}


          {/* Theme Toggle */}
          <button
            aria-label="Toggle theme"
            onClick={toggleTheme}
            className="relative h-9 w-9 inline-flex items-center justify-center rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.12] text-foreground/70 hover:text-foreground transition-all duration-200 cursor-pointer"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 transition-transform duration-200 hover:rotate-45" />
            ) : (
              <Moon className="w-4 h-4 transition-transform duration-200 hover:-rotate-12" />
            )}
          </button>

          {isLoggedIn ? (
            <button
              onClick={handleLogout}
              className="group inline-flex items-center gap-2 px-4 py-2 md:px-5 md:py-2.5 rounded-lg text-sm font-medium bg-white/[0.04] hover:bg-red-500/10 border border-white/[0.08] hover:border-red-500/30 text-foreground/70 hover:text-red-400 transition-all duration-200 cursor-pointer"
            >
              <LogOut className="w-4 h-4 transition-transform duration-200 group-hover:-translate-x-0.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          ) : (
            location.pathname === '/' && (
              <Link 
                to="/signup" 
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-lg shadow-red-500/20 hover:shadow-red-500/30 cursor-pointer"
              >
                Get Started
              </Link>
            )
          )}
        </div>
      </div>
    </nav>
  );
}
