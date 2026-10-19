import { Loader2, Sparkles } from 'lucide-react';
import type { VideoRead } from '../../api';
import EmptyState from '../../components/ui/EmptyState';
import TimeChip from '../../components/ui/TimeChip';

export default function OverviewPanel({ video, onSeek, onAsk }: {
  video: VideoRead;
  onSeek: (seconds: number) => void;
  onAsk: () => void;
}) {
  if (!video.summary && !video.key_points) {
    return video.transcript_available ? (
      <EmptyState icon={<Loader2 className="size-5 animate-spin" />} title="Writing the overview">It appears here in a minute or two.</EmptyState>
    ) : (
      <EmptyState icon={<Sparkles className="size-5" />} title="Overview pending">The overview is written once the transcript is ready.</EmptyState>
    );
  }
  return (
    <div className="space-y-5 px-1">
      {video.summary && <p className="text-sm leading-7">{video.summary}</p>}
      {video.key_points && (
        <section aria-labelledby="key-points">
          <h3 id="key-points" className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Key points</h3>
          <ol className="space-y-2.5">
            {video.key_points.map(point => (
              <li key={`${point.start_seconds}-${point.text}`} className="flex items-start gap-3">
                <TimeChip seconds={point.start_seconds} onClick={() => onSeek(point.start_seconds)} className="mt-0.5" />
                <span className="text-sm leading-6">{point.text}</span>
              </li>
            ))}
          </ol>
        </section>
      )}
      {video.overview_model && (
        <p className="text-xs text-muted-foreground">Written by {video.overview_model}</p>
      )}
      {video.suggested_questions && (
        <section aria-labelledby="questions">
          <h3 id="questions" className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Questions to ask</h3>
          <ul className="space-y-1.5">
            {video.suggested_questions.map(question => (
              <li key={question}>
                <button type="button" onClick={onAsk} className="text-left text-sm text-accent hover:underline">{question}</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
