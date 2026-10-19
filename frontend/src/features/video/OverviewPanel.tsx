import { AlertCircle, FileX, Loader2, RotateCw, Sparkles } from 'lucide-react';
import type { VideoRead } from '../../api';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import TimeChip from '../../components/ui/TimeChip';
import { useNotify } from '../../hooks/useNotify';
import { useRetryOverview } from './queries';

function RetryButton({ videoId }: { videoId: string }) {
  const retry = useRetryOverview(videoId);
  const notify = useNotify();
  return (
    <Button
      size="sm"
      disabled={retry.isPending}
      onClick={() => retry.mutate(undefined, {
        onError: error => notify.error(error, 'Overview not retried', 'Try again in a moment.'),
      })}
    >
      <RotateCw className="size-4" />Try again · free
    </Button>
  );
}

/** One line for an overview that is being rewritten or failed while an older one shows. */
function StatusLine({ video, signedIn }: { video: VideoRead; signedIn: boolean }) {
  if (video.overview_status === 'queued') {
    return (
      <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />Writing a new overview…
      </p>
    );
  }
  if (video.overview_status === 'failed') {
    return (
      <div role="status" className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <span className="flex items-center gap-2"><AlertCircle className="size-4 text-destructive" />The new overview could not be written.</span>
        {signedIn && <RetryButton videoId={video.video_id} />}
      </div>
    );
  }
  return null;
}

export default function OverviewPanel({ video, signedIn, onSeek, onAsk }: {
  video: VideoRead;
  signedIn: boolean;
  onSeek: (seconds: number) => void;
  onAsk: () => void;
}) {
  if (!video.summary && !video.key_points) {
    switch (video.overview_status) {
      case 'queued':
        return <EmptyState icon={<Loader2 className="size-5 animate-spin" />} title="Writing the overview">It appears here in a minute or two.</EmptyState>;
      case 'failed':
        return (
          <EmptyState
            icon={<AlertCircle className="size-5" />}
            title="The overview could not be written"
            action={signedIn ? <RetryButton videoId={video.video_id} /> : undefined}
          >
            {signedIn ? 'Trying again does not use credits.' : 'Sign in to try again.'}
          </EmptyState>
        );
      case 'no_transcript':
        return <EmptyState icon={<FileX className="size-5" />} title="No overview for this video">YouTube has no captions for it, so there is nothing to summarize.</EmptyState>;
      default:
        // A transcript but no queued overview, such as older videos the backfill skipped.
        if (video.transcript_status === 'ready') {
          return <EmptyState icon={<Sparkles className="size-5" />} title="No overview yet">You can still read the transcript or ask about the video.</EmptyState>;
        }
        return <EmptyState icon={<Sparkles className="size-5" />} title="Overview pending">The overview is written once the transcript is ready.</EmptyState>;
    }
  }
  return (
    <div className="space-y-5 px-1">
      <StatusLine video={video} signedIn={signedIn} />
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
