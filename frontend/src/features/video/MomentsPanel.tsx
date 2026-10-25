import { useLayoutEffect, useState } from 'react';
import { BookmarkPlus, Download } from 'lucide-react';
import { libraryApi } from '../../api';
import type { Arrival } from '../../hooks/useArrival';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import Spinner from '../../components/ui/Spinner';
import MomentItem from '../moments/MomentItem';
import { downloadText } from '../../lib/download';
import { useVideoMoments } from './queries';

export default function MomentsPanel({ videoId, onSeek, arrival, onArrivalShown }: {
  videoId: string;
  onSeek: (seconds: number) => void;
  /** The moment just reached, from a link or View moment. */
  arrival: Arrival<number> | null;
  onArrivalShown: (key: number) => void;
}) {
  const moments = useVideoMoments(videoId, true);
  const notify = useNotify();
  const [exporting, setExporting] = useState(false);

  // Scroll to an arrival once, when its row first appears; polling and remounts leave the list where it is.
  const arrived = arrival !== null && arrival.shownAt === null && Boolean(moments.data?.some(moment => moment.id === arrival.target));
  useLayoutEffect(() => {
    if (!arrived || !arrival) return;
    document.getElementById(`moment-${arrival.target}`)?.scrollIntoView({ block: 'center' });
    onArrivalShown(arrival.key);
  }, [arrived, arrival, onArrivalShown]);

  if (moments.isPending) return <div className="flex justify-center py-10"><Spinner /></div>;
  if (moments.isError) return <ErrorState compact title="Moments did not load" message="Check your connection and try again." onRetry={() => void moments.refetch()} />;
  if (!moments.data.length) {
    return (
      <EmptyState icon={<BookmarkPlus className="size-5" />} title="No moments yet">
        Press Save moment or S while the video plays, or save a line from the transcript or an answer.
      </EmptyState>
    );
  }

  const exportVideo = async () => {
    setExporting(true);
    try {
      downloadText(await libraryApi.exportVideo(videoId), `vidwiz-${videoId}.md`);
    } catch (cause) {
      notify.error(cause, 'Export failed', 'The moments could not be exported.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between pb-1">
        <p className="cursor-default text-xs text-muted-foreground tabular">{moments.data.length} {moments.data.length === 1 ? 'moment' : 'moments'}</p>
        <Button variant="ghost" size="sm" onClick={() => void exportVideo()} disabled={exporting}><Download className="size-3.5" />Markdown</Button>
      </div>
      <ul className="divide-y divide-border">
        {moments.data.map(moment => (
          // Every row is inset, so an arrival's tint and corners stay inside the panel.
          <MomentItem key={moment.id} moment={moment} onSeek={onSeek} arrivedAt={moment.id === arrival?.target ? arrival.shownAt : undefined} className="px-2.5" />
        ))}
      </ul>
    </div>
  );
}
