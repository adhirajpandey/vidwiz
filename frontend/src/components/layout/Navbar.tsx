import { useEffect, useState, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun, LogOut, LayoutDashboard, User, ChevronDown, Sparkles } from 'lucide-react';
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
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [profileImageUrl, setProfileImageUrl] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Decode JWT to get user info
  const decodeJwt = (token: string): { email?: string; name?: string; profile_image_url?: string } | null => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Failed to decode JWT', error);
      return null;
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsLoggedIn(true);
      const decoded = decodeJwt(token);
      if (decoded) {
        setDisplayName(decoded.name || decoded.email || null);
        setProfileImageUrl(decoded.profile_image_url || null);
      }
    } else {
      setIsLoggedIn(false);
      setDisplayName(null);
      setProfileImageUrl(null);
    }
  }, [location]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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
    setDisplayName(null);
    setProfileImageUrl(null);
    setIsDropdownOpen(false);
    navigate('/login');
  };

  const isActive = (path: string) => location.pathname === path;

  // Get first character for avatar
  const getAvatarChar = () => {
    if (displayName && displayName.length > 0) {
      return displayName.charAt(0).toUpperCase();
    }
    return 'U';
  };

  return (
    <nav className="fixed top-0 w-full z-50 select-none">
      {/* Subtle gradient background with glassmorphism */}
      <div className="absolute inset-0 bg-background/70 backdrop-blur-xl border-b border-white/[0.06]"></div>
      
      {/* Ambient top glow */}
      <div className="absolute inset-x-0 -top-20 h-20 bg-gradient-to-b from-red-500/5 to-transparent pointer-events-none"></div>
      
      <div className="relative max-w-screen-2xl mx-auto px-4 md:px-6 py-3 md:py-4 flex items-center justify-between">
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

        {/* Navigation Links - Center */}
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
                to="/wiz" 
                className={`group inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  location.pathname.startsWith('/wiz')
                    ? 'bg-white/[0.08] text-foreground' 
                    : 'text-foreground/60 hover:text-foreground hover:bg-white/[0.04]'
                }`}
              >
                <Sparkles className={`w-4 h-4 transition-colors ${location.pathname.startsWith('/wiz') ? 'text-violet-400' : 'group-hover:text-violet-400'}`} />
                Wiz
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
            /* User Avatar Dropdown */
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.04] transition-all duration-200 cursor-pointer"
                aria-label="User menu"
              >
                {/* Avatar */}
                <div className="relative">
                  {profileImageUrl ? (
                    <img 
                      src={profileImageUrl} 
                      alt={displayName || 'User'}
                      className="w-9 h-9 rounded-full shadow-lg shadow-red-500/25 transition-transform duration-200 group-hover:scale-105 object-cover"
                      onError={(e) => {
                        // Fallback to char avatar on image load error
                        e.currentTarget.style.display = 'none';
                        e.currentTarget.nextElementSibling?.classList.remove('hidden');
                      }}
                    />
                  ) : null}
                  <div className={`w-9 h-9 rounded-full bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center text-white font-semibold text-sm shadow-lg shadow-red-500/25 transition-transform duration-200 group-hover:scale-105 ${profileImageUrl ? 'hidden' : ''}`}>
                    {getAvatarChar()}
                  </div>
                  {/* Online indicator */}
                  <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-background"></div>
                </div>
                <ChevronDown className={`w-4 h-4 text-foreground/50 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-xl bg-card/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl shadow-black/20 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                  {/* User Info Header */}
                  <div className="px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
                    <div className="flex items-center gap-3">
                      {profileImageUrl ? (
                        <img 
                          src={profileImageUrl} 
                          alt={displayName || 'User'}
                          className="w-10 h-10 rounded-full object-cover"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                            e.currentTarget.nextElementSibling?.classList.remove('hidden');
                          }}
                        />
                      ) : null}
                      <div className={`w-10 h-10 rounded-full bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center text-white font-semibold text-base ${profileImageUrl ? 'hidden' : ''}`}>
                        {getAvatarChar()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">{displayName || 'User'}</p>
                        <p className="text-xs text-foreground/50">Manage your account</p>
                      </div>
                    </div>
                  </div>

                  {/* Menu Items */}
                  <div className="py-1.5">
                    <Link
                      to="/profile"
                      onClick={() => setIsDropdownOpen(false)}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150 ${
                        isActive('/profile')
                          ? 'bg-white/[0.06] text-foreground'
                          : 'text-foreground/70 hover:text-foreground hover:bg-white/[0.04]'
                      }`}
                    >
                      <User className={`w-4 h-4 ${isActive('/profile') ? 'text-red-400' : ''}`} />
                      <span>Profile</span>
                    </Link>
                    
                    <div className="my-1.5 mx-3 border-t border-white/[0.06]"></div>
                    
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-foreground/70 hover:text-red-400 hover:bg-red-500/10 transition-all duration-150 cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Logout</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
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
