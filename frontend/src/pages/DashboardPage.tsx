import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import VideoCard from '../components/VideoCard';
import { FaSearch, FaYoutube, FaVideo, FaChevronLeft, FaChevronRight } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi2';
import { getUserFromToken, removeToken } from '../lib/authUtils';
import { videosApi } from '../api';
import type { VideoSearchItem } from '../api/types';
import config from '../config';
import Seo from '../components/Seo';

export default function DashboardPage() {
  const [user, setUser] = useState<{ email: string; name?: string } | null>(null);
  const [videos, setVideos] = useState<VideoSearchItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [hasAnyVideos, setHasAnyVideos] = useState(true); // assume true until initial fetch
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalVideos, setTotalVideos] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    const userInfo = getUserFromToken();
    if (userInfo?.email) {
      setUser({ email: userInfo.email, name: userInfo.name });
    } else {
      // Invalid or expired token, redirect to login
      removeToken();
      navigate('/login');
    }
  }, [navigate]);

  // Fetch initial videos on page load
  useEffect(() => {
    if (user) {
      fetchPage(1, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const fetchPage = async (page: number, isInitial = false) => {
    setIsSearching(true);
    try {
      // API client automatically handles auth token
      const data = await videosApi.listVideos({
        q: searchQuery,
        page,
        per_page: 10,
      });

      setVideos(data.videos);
      setCurrentPage(data.page);
      setTotalPages(data.total_pages);
      setTotalVideos(data.total);
      if (isInitial) {
        setHasAnyVideos(data.total > 0);
      }
    } catch (error: any) {
       // 401 handling is done by client interceptor but we can add specific logic if needed
       // client interceptor might redirect, so we might just log here
       console.error('Failed to fetch videos', error);
       setVideos([]);
       setTotalPages(0);
       setTotalVideos(0);
    } finally {
      setIsSearching(false);
      setHasSearched(true);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    await fetchPage(1);
  };

  return (
    <>
      <Seo
        title="Dashboard: Your Smart Notes Library | VidWiz"
        description="Search, manage, and revisit your Smart Notes across saved YouTube videos in your VidWiz dashboard."
        path="/dashboard"
        noIndex
      />
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
                <span className="text-sm font-medium text-foreground/80">Welcome back, <span className="text-foreground">{user.name || user.email}</span></span>
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
                <h3 className="text-base md:text-lg font-semibold text-foreground tracking-tight">Your Videos</h3>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 md:px-2.5 md:py-1 rounded-md text-[11px] md:text-xs font-medium bg-white/[0.06] text-foreground/60 border border-white/[0.08]">
                {totalVideos} {totalVideos === 1 ? 'video' : 'videos'}
              </span>
            </div>
            
            {/* Results list */}
            <div className="p-3 md:p-5">
              {videos.length === 0 ? (
                !hasAnyVideos ? (
                  /* Onboarding: user has no saved videos yet */
                  <div className="text-center py-10 md:py-14 px-4 select-none">
                    <div className="relative inline-block mb-5">
                      {/* Animated glow ring */}
                      <div className="absolute inset-0 bg-gradient-to-r from-blue-500/30 to-blue-600/30 rounded-2xl blur-xl animate-pulse"></div>
                      <div className="relative w-16 h-16 md:w-20 md:h-20 mx-auto rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/20 flex items-center justify-center">
                        {/* Chrome Web Store icon */}
                        <svg className="w-8 h-8 md:w-10 md:h-10 flex-shrink-0" viewBox="0 0 192 192" xmlns="http://www.w3.org/2000/svg">
                          <path d="M58 24c-8 0-14 6-14 14v4H28c-3 0-5 2-5 5l-7 90c0 3 1 5 3 7s5 3 7 3h140c3 0 5-1 7-3s3-4 3-7l-7-90c0-3-2-5-5-5h-16v-4c0-8-6-14-14-14H58z" fill="#4285F4"/>
                          <path d="M96 88a36 36 0 100 72 36 36 0 000-72z" fill="white"/>
                          <path d="M96 96a28 28 0 00-24 14l14 8a14 14 0 0124 0l14-8a28 28 0 00-28-14z" fill="#EA4335"/>
                          <path d="M72 110a28 28 0 000 28l14-8a14 14 0 010-12l-14-8z" fill="#4285F4"/>
                          <path d="M96 152a28 28 0 0024-14l-14-8a14 14 0 01-24 0l-14 8a28 28 0 0028 14z" fill="#34A853"/>
                          <path d="M120 138a28 28 0 000-28l-14 8a14 14 0 010 12l14 8z" fill="#FBBC05"/>
                          <circle cx="96" cy="124" r="8" fill="#4285F4"/>
                        </svg>
                      </div>
                    </div>
                    <h3 className="text-lg md:text-xl font-semibold text-foreground mb-2">Get Started with VidWiz</h3>
                    <p className="text-foreground/40 text-sm max-w-md mx-auto mb-6">
                      Install the Chrome extension, open any YouTube video, and start taking notes - they'll show up right here.
                    </p>
                    <a
                      href={config.CHROME_WEBSTORE_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group inline-flex items-center gap-2.5 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-xl hover:bg-right transition-all duration-500 shadow-lg shadow-red-500/25 hover:shadow-red-500/40"
                    >
                      Install Chrome Extension
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </a>
                    <div className="mt-4">
                      <Link to="/help" className="inline-flex items-center gap-1 text-sm text-purple-400 hover:text-purple-300 transition-colors">
                        See how it works <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                ) : (
                  /* Empty search results */
                  <div className="text-center py-10 md:py-14 select-none">
                    <div className="w-14 h-14 md:w-16 md:h-16 mx-auto mb-3 md:mb-4 rounded-xl bg-white/[0.04] flex items-center justify-center">
                      <FaVideo className="w-7 h-7 md:w-8 md:h-8 text-foreground/20" />
                    </div>
                    <p className="text-foreground/50 text-sm font-medium">No videos found</p>
                    <p className="text-foreground/30 text-xs mt-1">Try a different search term</p>
                  </div>
                )
              ) : (
                <div className="space-y-2 md:space-y-3">
                  {videos.map((video) => (
                    <VideoCard key={video.video_id} video={video} />
                  ))}

                  {/* Pagination Controls */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-center gap-4 pt-4 mt-4 border-t border-white/[0.06]">
                      <button
                        onClick={() => fetchPage(currentPage - 1)}
                        disabled={currentPage <= 1 || isSearching}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground/70 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 cursor-pointer"
                      >
                        <FaChevronLeft className="w-3 h-3" />
                        <span>Previous</span>
                      </button>
                      <span className="text-sm text-foreground/60 font-medium">
                        Page {currentPage} of {totalPages}
                      </span>
                      <button
                        onClick={() => fetchPage(currentPage + 1)}
                        disabled={currentPage >= totalPages || isSearching}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground/70 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 cursor-pointer"
                      >
                        <span>Next</span>
                        <FaChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        </div>
      </div>
    </>
  );
}
