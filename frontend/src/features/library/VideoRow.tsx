import { Link } from 'react-router-dom';
import type { LibraryVideo } from '../../api';
import Thumbnail from '../../components/ui/Thumbnail';
import { formatRelative, videoTitle } from '../../lib/format';

export default function VideoRow({ video }: { video: LibraryVideo }) {
  const channel = video.metadata?.uploader;
  return (
    <Link to={`/v/${video.video_id}`} className="flex items-center gap-3 rounded-lg p-2 hover:bg-muted">
      <Thumbnail videoId={video.video_id} className="w-28 sm:w-36" />
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-sm font-medium leading-5">{videoTitle(video.title, video.video_id)}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {[channel, `${video.moment_count} ${video.moment_count === 1 ? 'moment' : 'moments'}`, formatRelative(video.last_activity_at)]
            .filter(Boolean)
            .join(' · ')}
        </p>
        {!video.transcript_available && <p className="mt-0.5 text-xs text-muted-foreground">Transcript pending</p>}
      </div>
    </Link>
  );
}
