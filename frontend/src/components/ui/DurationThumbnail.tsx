import type { LibraryVideo } from '../../api';
import { formatClock } from '../../lib/format';
import Thumbnail from './Thumbnail';

/** Thumbnail with the duration in its corner, like YouTube. */
export default function DurationThumbnail({ video, className }: { video: LibraryVideo; className?: string }) {
  const duration = video.metadata?.duration;
  return (
    <div className={`relative shrink-0 ${className ?? ''}`}>
      <Thumbnail videoId={video.video_id} className="w-full" />
      {duration ? (
        <span className="absolute bottom-1 right-1 rounded-[4px] bg-black/75 px-1 py-px text-[11px] font-semibold leading-4 text-white tabular">{formatClock(duration)}</span>
      ) : null}
    </div>
  );
}
