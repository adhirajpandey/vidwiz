import { Link } from 'react-router-dom';
import { FaPlay, FaExternalLinkAlt, FaStickyNote } from 'react-icons/fa';

interface VideoCardProps {
  video: {
    video_id: string;
    video_title: string;
    metadata?: {
      channel?: string;
      thumbnail?: string;
      duration_string?: string;
    };
  };
}

export default function VideoCard({ video }: VideoCardProps) {
  const thumbnailUrl = video.metadata?.thumbnail || 
    `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`;

  return (
    <div className="group relative bg-card hover:bg-muted/50 rounded-xl border border-border hover:border-border/80 transition-all duration-300 overflow-hidden select-none">
      <div className="flex items-center gap-3 md:gap-4 p-3 md:p-4">
        {/* Thumbnail */}
        <a
          href={`https://www.youtube.com/watch?v=${video.video_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="relative flex-shrink-0 w-24 md:w-32 aspect-video rounded-lg overflow-hidden group/thumb bg-muted"
        >
          <img 
            src={thumbnailUrl} 
            alt={video.video_title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover/thumb:scale-110"
          />
          {/* Overlay on hover */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 transition-opacity duration-300 flex items-center justify-center">
            <div className="w-8 h-8 rounded-full bg-red-600/90 flex items-center justify-center shadow-lg">
              <FaPlay className="w-3 h-3 text-white ml-0.5" />
            </div>
          </div>
          {/* Duration badge */}
          {video.metadata?.duration_string && (
            <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/80 rounded text-[10px] text-white font-medium select-none">
              {video.metadata.duration_string}
            </div>
          )}
        </a>

        {/* Content */}
        <div className="flex-grow min-w-0 py-0.5">
          {/* Title */}
          <a
            href={`https://www.youtube.com/watch?v=${video.video_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm md:text-base font-medium text-foreground hover:text-red-400 transition-colors duration-200 line-clamp-2 leading-snug"
          >
            {video.video_title}
            <FaExternalLinkAlt className="inline-block w-2.5 h-2.5 ml-1.5 opacity-0 group-hover:opacity-50 transition-opacity" />
          </a>
          
          {/* Channel badge */}
          {video.metadata?.channel && (
            <span className="inline-flex items-center mt-2 px-2 py-0.5 rounded-md text-[11px] font-medium bg-red-500/10 text-red-400/80 border border-red-500/10">
              {video.metadata.channel}
            </span>
          )}
        </div>

        {/* View Notes button */}
        <Link
          to={`/dashboard/${video.video_id}`}
          className="flex-shrink-0 inline-flex items-center gap-2 px-3 py-2 md:px-4 md:py-2.5 text-xs md:text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-md shadow-red-500/20 hover:shadow-lg hover:shadow-red-500/30 cursor-pointer"
        >
          <FaStickyNote className="w-3 h-3 md:w-3.5 md:h-3.5" />
          <span className="hidden sm:inline">View Notes</span>
          <span className="sm:hidden">Notes</span>
        </Link>
      </div>
    </div>
  );
}
