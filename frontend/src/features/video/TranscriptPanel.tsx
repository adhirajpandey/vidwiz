import { useEffect, useMemo, useRef, useState } from 'react';
import { Bookmark, BookmarkCheck, FileText, Loader2 } from 'lucide-react';
import type { TranscriptSegment } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import Spinner from '../../components/ui/Spinner';
import { formatClock } from '../../lib/format';
import { cn } from '../../lib/utils';
import { useSavePassage } from '../moments/queries';
import { useTranscript } from './queries';
import { activeSegment } from './activeSegment';

function Line({ segment, active, query, onSeek, signedIn, videoId }: {
  segment: TranscriptSegment;
  active: boolean;
  query: string;
  onSeek: (seconds: number) => void;
  signedIn: boolean;
  videoId: string;
}) {
  const save = useSavePassage();
  const notify = useNotify();
  const [saved, setSaved] = useState(false);
  const text = useMemo(() => highlight(segment.text, query), [segment.text, query]);
  return (
    <li data-active={active || undefined} className={cn('group flex items-start gap-2 rounded-md px-1.5 py-1', active && 'bg-accent-soft')}>
      <button
        type="button"
        onClick={() => onSeek(segment.start_seconds)}
        className="w-12 shrink-0 pt-0.5 text-left font-mono text-xs text-muted-foreground tabular hover:text-accent"
        aria-label={`Play from ${formatClock(segment.start_seconds)}`}
      >
        {formatClock(segment.start_seconds)}
      </button>
      <p className="flex-1 text-sm leading-6">{text}</p>
      {signedIn && (
        <button
          type="button"
          disabled={save.isPending || saved}
          aria-label={saved ? 'Saved as a moment' : 'Save line as a moment'}
          title={saved ? 'Saved as a moment' : 'Save as a moment (free)'}
          onClick={() => save.mutate(
            { video_id: videoId, start_seconds: segment.start_seconds, end_seconds: segment.end_seconds },
            {
              onSuccess: () => setSaved(true),
              onError: error => notify.error(error, 'Line not saved', 'The line could not be saved.'),
            },
          )}
          className={cn('rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground', !saved && 'opacity-0 group-hover:opacity-100 focus:opacity-100')}
        >
          {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : saved ? <BookmarkCheck className="size-3.5 text-accent" /> : <Bookmark className="size-3.5" />}
        </button>
      )}
    </li>
  );
}

function highlight(text: string, query: string) {
  if (query.length < 2) return text;
  const lower = text.toLowerCase();
  const parts = [];
  let cursor = 0;
  let index = lower.indexOf(query);
  while (index !== -1) {
    parts.push(text.slice(cursor, index));
    parts.push(<mark key={index} className="rounded-sm bg-accent/20 text-foreground">{text.slice(index, index + query.length)}</mark>);
    cursor = index + query.length;
    index = lower.indexOf(query, cursor);
  }
  parts.push(text.slice(cursor));
  return parts;
}

export default function TranscriptPanel({ videoId, playhead, onSeek, signedIn }: {
  videoId: string;
  playhead: number | null;
  onSeek: (seconds: number) => void;
  signedIn: boolean;
}) {
  const transcript = useTranscript(videoId, true);
  const [query, setQuery] = useState('');
  const list = useRef<HTMLOListElement>(null);
  const segments = useMemo(() => transcript.data?.segments ?? [], [transcript.data]);
  const needle = query.trim().toLowerCase();
  const visible = needle.length >= 2 ? segments.filter(segment => segment.text.toLowerCase().includes(needle)) : segments;
  const current = needle.length >= 2 ? -1 : activeSegment(segments, playhead);

  // Keep the playing line in view, unless the user is searching.
  useEffect(() => {
    if (current < 0) return;
    list.current?.querySelector('[data-active]')?.scrollIntoView({ block: 'nearest' });
  }, [current]);

  if (transcript.isPending) return <div className="flex justify-center py-10"><Spinner /></div>;
  if (transcript.isError) return <ErrorState compact title="The transcript did not load" message="Check your connection and try again." onRetry={() => void transcript.refetch()} />;
  if (transcript.data.status === 'processing') {
    return <EmptyState icon={<Loader2 className="size-5 animate-spin" />} title="Fetching the transcript">This usually takes under a minute.</EmptyState>;
  }
  if (transcript.data.status === 'unavailable' || !segments.length) {
    return <EmptyState icon={<FileText className="size-5" />} title="No transcript for this video">YouTube has no captions for it, so search, Ask, and AI lines are not available.</EmptyState>;
  }

  return (
    <div className="space-y-2">
      <Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Find in transcript" aria-label="Find in transcript" className="h-9" />
      {needle.length >= 2 && <p className="px-1 text-xs text-muted-foreground tabular">{visible.length} matching lines</p>}
      <ol ref={list} className="space-y-0.5">
        {visible.map(segment => (
          <Line
            key={`${segment.start_seconds}-${segment.text.slice(0, 12)}`}
            segment={segment}
            active={segments[current] === segment}
            query={needle}
            onSeek={onSeek}
            signedIn={signedIn}
            videoId={videoId}
          />
        ))}
      </ol>
    </div>
  );
}
