import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import config from '../config';
import VideoCard from '../components/VideoCard';
import { FaSearch, FaYoutube, FaVideo } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi2';

export default function DashboardPage() {
  const [user, setUser] = useState<{ username: string } | null>(null);
  const [videos, setVideos] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();

  // Decode JWT to get username (avoid API call)
  const decodeJwt = (token: string): { username?: string } | null => {
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
      const decoded = decodeJwt(token);
      if (decoded?.username) {
        setUser({ username: decoded.username });
      } else {
        // Invalid token, redirect to login
        localStorage.removeItem('token');
        navigate('/login');
      }
    } else {
      navigate('/login');
    }
  }, [navigate]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSearching(true);
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await fetch(`${config.API_URL}/search?query=${searchQuery}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setVideos(data);
        } else if (response.status === 401) {
          // Token expired, clear and redirect to login
          localStorage.removeItem('token');
          navigate('/login');
          return;
        } else {
          setVideos([]);
        }
      } catch (error) {
        console.error('Failed to fetch videos', error);
      }
    }
    setIsSearching(false);
    setHasSearched(true);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12">
        {/* Hero Section */}
        <div className="relative mb-8 md:mb-12">
          {/* Ambient background glow */}
          <div className="absolute -inset-4 bg-gradient-to-r from-red-500/10 via-purple-500/5 to-red-500/10 rounded-3xl blur-2xl opacity-60"></div>
          
          <div className="relative">
            {/* Welcome badge */}
            {user && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-4 rounded-full bg-gradient-to-r from-white/[0.08] to-white/[0.04] border border-white/[0.08] select-none">
                <HiSparkles className="w-3.5 h-3.5 text-violet-400" />
                <span className="text-sm font-medium text-foreground/80">Welcome back, <span className="text-foreground">{user.username}</span></span>
              </div>
            )}
            
            {/* Title */}
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight select-none">
              <span className="bg-gradient-to-r from-foreground via-foreground to-foreground/70 bg-clip-text text-transparent">
                Search Your
              </span>
              <span className="bg-gradient-to-r from-red-500 to-red-600 bg-clip-text text-transparent"> Video Notes</span>
            </h1>
            <p className="mt-2 text-foreground/50 text-sm md:text-base select-none">
              Find and manage notes from your saved YouTube videos
            </p>
          </div>
        </div>

        {/* Search Section */}
        <div className="relative mb-8 md:mb-10">
          <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-xl md:rounded-2xl shadow-xl overflow-hidden border border-white/[0.08] select-none">
            {/* Subtle inner glow */}
            <div className="absolute inset-0 bg-gradient-to-r from-red-500/5 via-transparent to-red-500/5 pointer-events-none"></div>
            
            <div className="relative p-4 md:p-6">
              <form onSubmit={handleSearch} className="w-full">
                <div className="relative group">
                  {/* Search icon */}
                  <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
                    <FaSearch className="w-4 h-4 text-foreground/30 group-focus-within:text-red-400 transition-colors duration-300" />
                  </div>
                  
                  {/* Input field */}
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="block w-full p-4 pl-11 pr-36 text-sm md:text-base text-foreground bg-white/[0.04] border border-white/[0.08] rounded-xl focus:ring-2 focus:ring-red-500/30 focus:border-red-500/50 focus:bg-white/[0.06] placeholder:text-foreground/30 transition-all duration-300"
                    placeholder="Search by video title"
                  />
                  
                  {/* Search button */}
                  <button
                    type="submit"
                    disabled={isSearching}
                    className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-lg shadow-red-500/25 hover:shadow-red-500/40 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {isSearching ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                        <span>Searching</span>
                      </>
                    ) : (
                      <>
                        <FaSearch className="w-3.5 h-3.5" />
                        <span>Search</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>

        {/* Results Section */}
        {hasSearched && (
          <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-xl md:rounded-2xl shadow-xl overflow-hidden border border-white/[0.08] select-none">
            {/* Header */}
            <div className="px-4 py-3 md:px-6 md:py-4 border-b border-white/[0.06] bg-white/[0.02] flex items-center justify-between select-none">
              <div className="flex items-center gap-2.5 md:gap-3">
                <div className="w-7 h-7 md:w-8 md:h-8 rounded-lg bg-gradient-to-br from-red-500/20 to-red-600/20 flex items-center justify-center flex-shrink-0">
                  <FaYoutube className="w-3.5 h-3.5 md:w-4 md:h-4 text-red-400" />
                </div>
                <h3 className="text-base md:text-lg font-semibold text-foreground tracking-tight">Search Results</h3>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 md:px-2.5 md:py-1 rounded-md text-[11px] md:text-xs font-medium bg-white/[0.06] text-foreground/60 border border-white/[0.08]">
                {videos.length} {videos.length === 1 ? 'video' : 'videos'}
              </span>
            </div>
            
            {/* Results list */}
            <div className="p-3 md:p-5">
              {videos.length === 0 ? (
                <div className="text-center py-10 md:py-14 select-none">
                  <div className="w-14 h-14 md:w-16 md:h-16 mx-auto mb-3 md:mb-4 rounded-xl bg-white/[0.04] flex items-center justify-center">
                    <FaVideo className="w-7 h-7 md:w-8 md:h-8 text-foreground/20" />
                  </div>
                  <p className="text-foreground/50 text-sm font-medium">No videos found</p>
                  <p className="text-foreground/30 text-xs mt-1">Try a different search term</p>
                </div>
              ) : (
                <div className="space-y-2 md:space-y-3">
                  {videos.map((video) => (
                    <VideoCard key={video.video_id} video={video} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Initial state - before any search */}
        {!hasSearched && (
          <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-xl md:rounded-2xl shadow-xl overflow-hidden border border-white/[0.08] select-none">
            <div className="text-center py-14 md:py-20 px-6 select-none">
              <div className="relative inline-block mb-6">
                {/* Animated glow ring */}
                <div className="absolute inset-0 bg-gradient-to-r from-red-500/30 to-red-600/30 rounded-2xl blur-xl animate-pulse"></div>
                <div className="relative w-16 h-16 md:w-20 md:h-20 mx-auto rounded-2xl bg-gradient-to-br from-red-500/20 to-red-600/10 border border-red-500/20 flex items-center justify-center">
                  <FaYoutube className="w-8 h-8 md:w-10 md:h-10 text-red-400" />
                </div>
              </div>
              <h3 className="text-lg md:text-xl font-semibold text-foreground mb-2">Start Searching</h3>
              <p className="text-foreground/40 text-sm max-w-md mx-auto">
                Search for videos by title to view and manage your AI-generated and personal notes
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
