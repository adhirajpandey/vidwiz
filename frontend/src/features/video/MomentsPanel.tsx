import { useEffect, useState } from 'react';
import { BookmarkPlus, Download } from 'lucide-react';
import { libraryApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import Spinner from '../../components/ui/Spinner';
import MomentItem from '../moments/MomentItem';
import { downloadText } from '../../lib/download';
import { useVideoMoments } from './queries';

export default function MomentsPanel({ videoId, onSeek, highlightId }: {
  videoId: string;
  onSeek: (seconds: number) => void;
  highlightId: number | null;
}) {
  const moments = useVideoMoments(videoId, true);
  const notify = useNotify();
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (highlightId && moments.data) {
      document.getElementById(`moment-${highlightId}`)?.scrollIntoView({ block: 'center' });
    }
  }, [highlightId, moments.data]);

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
      <div className="flex items-center justify-between px-1 pb-1">
        <p className="text-xs text-muted-foreground tabular">{moments.data.length} {moments.data.length === 1 ? 'moment' : 'moments'}</p>
        <Button variant="ghost" size="sm" onClick={() => void exportVideo()} disabled={exporting}><Download className="size-3.5" />Markdown</Button>
      </div>
      <ul className="divide-y divide-border">
        {moments.data.map(moment => (
          <MomentItem key={moment.id} moment={moment} onSeek={onSeek} highlighted={moment.id === highlightId} />
        ))}
      </ul>
    </div>
  );
}
