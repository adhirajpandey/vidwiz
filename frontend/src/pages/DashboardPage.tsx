import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import config from '../config';
import VideoCard from '../components/VideoCard';

export default function DashboardPage() {
  const [user, setUser] = useState<{ username: string } | null>(null);
  const [videos, setVideos] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProfile = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const response = await fetch(`${config.API_URL}/user/profile`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            setUser(data);
          } else {
            // Handle error, e.g., token expired
            localStorage.removeItem('token');
            navigate('/login');
          }
        } catch (error) {
          console.error('Failed to fetch profile', error);
        }
      }
    };

    fetchProfile();
  }, [navigate]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
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
        } else {
          setVideos([]);
        }
      } catch (error) {
        console.error('Failed to fetch videos', error);
      }
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="flex justify-between items-center">
          <h1 className="text-4xl font-bold">Dashboard</h1>
        </div>
        {user && <p className="mt-4 text-lg">Welcome, {user.username}!</p>}

        <div className="mt-8">
          <form onSubmit={handleSearch} className="w-full">
            <div className="relative">
              <div className="absolute inset-y-0 start-0 flex items-center ps-3 pointer-events-none">
                <svg className="w-4 h-4 text-gray-500" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 20 20">
                  <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="m19 19-4-4m0-7A7 7 0 1 1 1 8a7 7 0 0 1 14 0Z"/>
                </svg>
              </div>
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="block w-full p-4 ps-10 text-sm text-foreground border border-input rounded-lg bg-background focus:ring-red-500 focus:border-red-500"
                placeholder="Search Videos..."
              />
              <button
                type="submit"
                className="text-white absolute end-2.5 bottom-2.5 bg-red-500 hover:bg-red-600 font-medium rounded-lg text-sm px-4 py-2 transition-colors cursor-pointer"
              >
                Search
              </button>
            </div>
          </form>
        </div>

        <div className="mt-8 space-y-4">
          {videos.map((video) => (
            <VideoCard key={video.video_id} video={video} />
          ))}
        </div>
      </div>
    </div>
  );
}
