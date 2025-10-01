import { Link } from 'react-router-dom';

interface VideoCardProps {
  video: {
    video_id: string;
    video_title: string;
  };
}

export default function VideoCard({ video }: VideoCardProps) {
  return (
    <div className="flex items-center p-4 bg-card border rounded-lg shadow-sm">
      <a
        href={`https://www.youtube.com/watch?v=${video.video_id}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-foreground font-medium flex-grow pr-4"
      >
        {video.video_title}
      </a>
      <Link
        to={`/dashboard/${video.video_id}`}
        className="flex-shrink-0 inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-md hover:bg-red-600 transition-colors cursor-pointer"
      >
        View Notes
      </Link>
    </div>
  );
}
