import { HelpCircle } from 'lucide-react';
import type { MomentRead } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import Thumbnail from '../../components/ui/Thumbnail';
import { formatClock, videoTitle } from '../../lib/format';
import { useResolveMoment } from './queries';

/** A title capture matched several videos; the user picks the right one. */
export default function ResolvePicker({ moment }: { moment: MomentRead }) {
  const resolve = useResolveMoment();
  const notify = useNotify();
  const candidates = moment.resolve_candidates ?? [];

  if (!candidates.length) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <HelpCircle className="size-4" />
        No video found for “{moment.pending_title}”. Capture it again from the video page.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm">
        Which video did you capture at {formatClock(moment.at_seconds)}?
        <span className="text-muted-foreground"> “{moment.pending_title}”</span>
      </p>
      <ul className="space-y-1">
        {candidates.map(candidate => (
          <li key={candidate.video_id}>
            <button
              type="button"
              disabled={resolve.isPending}
              onClick={() => resolve.mutate(
                { id: moment.id, videoId: candidate.video_id },
                {
                  onError: error => notify.error(error, 'Video not chosen', 'That video could not be chosen.'),
                },
              )}
              className="flex w-full items-center gap-3 rounded-lg p-1.5 text-left hover:bg-muted disabled:opacity-60"
            >
              <Thumbnail videoId={candidate.video_id} className="w-20" />
              <span className="min-w-0">
                <span className="line-clamp-2 text-sm font-medium">{videoTitle(candidate.title, candidate.video_id)}</span>
                {candidate.channel && <span className="block text-xs text-muted-foreground">{candidate.channel}</span>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
