import { formatClock } from '../../lib/format';
import { startSeconds } from '../moments/queries';
import { useVideoMoments } from './queries';

/** Where your moments sit in the video: caption-yellow marks on a thin rail. */
export default function MomentStrip({ videoId, duration, playhead, onSeek }: {
  videoId: string;
  duration: number;
  playhead: number | null;
  onSeek: (seconds: number) => void;
}) {
  const moments = useVideoMoments(videoId, true);
  const at = (seconds: number) => `${Math.min(100, (seconds / duration) * 100)}%`;
  const marks = (moments.data ?? []).filter(moment => moment.resolve_status === 'resolved');
  return (
    <div className="relative h-4" aria-label="Your moments in this video">
      <div className="absolute inset-x-0 top-1.5 h-1 rounded-full bg-border" />
      {playhead !== null && <div className="absolute left-0 top-1.5 h-1 rounded-full bg-muted-foreground/60" style={{ width: at(playhead) }} />}
      {marks.map(moment => {
        const start = startSeconds(moment);
        return (
          <button
            key={moment.id}
            type="button"
            onClick={() => onSeek(start)}
            aria-label={`Play moment at ${formatClock(start)}`}
            title={moment.ai_text ?? moment.note ?? formatClock(start)}
            className="absolute top-0 h-4 w-1 -translate-x-1/2 rounded-full bg-saved shadow-[0_0_0_1.5px_hsl(var(--background))] hover:scale-y-125"
            style={{ left: at(start) }}
          />
        );
      })}
    </div>
  );
}
