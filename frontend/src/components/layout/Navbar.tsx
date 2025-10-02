import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
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

  return (
    <nav className="fixed top-0 w-full bg-background/80 backdrop-blur-md border-b border-border z-50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <img src={vidwizLogo} alt="VidWiz" className="w-8 h-8" />
          <span className="text-2xl font-bold text-foreground">VidWiz</span>
        </Link>
        <div className="hidden md:flex items-center gap-8">
          {isLoggedIn ? (
            <>
              <Link to="/dashboard" className="text-muted-foreground hover:text-foreground transition-colors">Dashboard</Link>
              <Link to="/profile" className="text-muted-foreground hover:text-foreground transition-colors">Profile</Link>
            </>
          ) : (
            location.pathname === '/' && (
              <>
                <a href="#features" className="text-muted-foreground hover:text-foreground transition-colors">Features</a>
                <a href="#how-it-works" className="text-muted-foreground hover:text-foreground transition-colors">How It Works</a>
              </>
            )
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            aria-label="Toggle theme"
            onClick={toggleTheme}
            className="h-9 w-9 inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground text-foreground transition-colors cursor-pointer"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          {isLoggedIn ? (
            <button
              onClick={handleLogout}
              className="bg-background text-foreground/80 px-6 py-2.5 rounded-lg font-medium hover:bg-accent transition-all border border-border hover:border-foreground/30 cursor-pointer"
            >
              Logout
            </button>
          ) : (
            location.pathname === '/' && (
              <Link to="/signup" className="bg-red-500 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-600 transition-all hover:shadow-lg hover:shadow-red-500/25 cursor-pointer">
                Get Started
              </Link>
            )
          )}
        </div>
      </div>
    </nav>
  );
}
