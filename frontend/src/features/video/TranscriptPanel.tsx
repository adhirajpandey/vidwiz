import { useEffect, useMemo, useRef, useState } from 'react';
import { Bookmark, BookmarkCheck, FileText, Loader2 } from 'lucide-react';
import type { TranscriptSegment } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import { Tooltip } from '../../components/ui/Tooltip';
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
    <li data-active={active || undefined} className={cn('group flex items-start gap-2 rounded-md px-1.5 py-1 transition-colors duration-200', active && 'bg-accent-soft')}>
      <button
        type="button"
        onClick={() => onSeek(segment.start_seconds)}
        className="w-12 shrink-0 pt-0.5 text-left text-xs font-semibold text-muted-foreground tabular hover:text-foreground"
        aria-label={`Play from ${formatClock(segment.start_seconds)}`}
      >
        {formatClock(segment.start_seconds)}
      </button>
      <p className="flex-1 text-sm leading-6">{text}</p>
      {signedIn && (
        <Tooltip label={saved ? 'Saved as a moment' : 'Save as a moment, free'} side="left">
        <button
          type="button"
          disabled={save.isPending || saved}
          aria-label={saved ? 'Saved as a moment' : 'Save line as a moment'}
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
        </Tooltip>
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
    parts.push(<mark key={index} className="rounded-sm bg-saved text-saved-foreground">{text.slice(index, index + query.length)}</mark>);
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
  const [following, setFollowing] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);
  const followedTop = useRef(0);
  const hasCentered = useRef(false);
  const list = useRef<HTMLOListElement>(null);
  const segments = useMemo(() => transcript.data?.segments ?? [], [transcript.data]);
  const needle = query.trim().toLowerCase();
  const visible = needle.length >= 2 ? segments.filter(segment => segment.text.toLowerCase().includes(needle)) : segments;
  const current = needle.length >= 2 ? -1 : activeSegment(segments, playhead);

  // Scroll only the transcript, never its ancestors or the page.
  useEffect(() => {
    const container = scroller.current;
    const lines = list.current;
    if (current < 0 || !following || !container || !lines) return;
    let cancelled = false;
    let frame = 0;
    const center = () => {
      if (cancelled) return;
      const row = lines.querySelector<HTMLElement>('[data-active]');
      if (!row || !container.clientHeight) return;
      const offset = row.getBoundingClientRect().top - container.getBoundingClientRect().top - container.clientTop;
      const top = container.scrollTop + offset + row.offsetHeight / 2 - container.clientHeight / 2;
      const target = Math.max(0, Math.min(top, container.scrollHeight - container.clientHeight));
      const start = container.scrollTop;
      cancelAnimationFrame(frame);
      const move = (position: number) => {
        followedTop.current = position;
        container.scrollTop = position;
      };
      // Snap on entry and large seeks; ease the short moves between lines.
      const animate = hasCentered.current && Math.abs(target - start) < container.clientHeight
        && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      hasCentered.current = true;
      if (!animate || Math.abs(target - start) < 1) { move(target); return; }
      const started = performance.now();
      const step = (now: number) => {
        if (cancelled) return;
        const progress = Math.min(1, (now - started) / 240);
        move(start + (target - start) * (1 - (1 - progress) ** 3));
        if (progress < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    };
    center();
    const observer = new ResizeObserver(center);
    observer.observe(container);
    observer.observe(lines);
    return () => { cancelled = true; cancelAnimationFrame(frame); observer.disconnect(); };
  }, [current, following, segments]);

  if (transcript.isPending) return <div className="flex justify-center py-10"><Spinner /></div>;
  if (transcript.isError) return <ErrorState compact title="The transcript did not load" message="Check your connection and try again." onRetry={() => void transcript.refetch()} />;
  if (transcript.data.status === 'pending') {
    return <EmptyState icon={<Loader2 className="size-5 animate-spin" />} title="Fetching the transcript">This usually takes under a minute.</EmptyState>;
  }
  if (transcript.data.status === 'unavailable' || !segments.length) {
    return <EmptyState icon={<FileText className="size-5" />} title="Transcript unavailable">VidWiz could not get a transcript for this video, so search, Ask, and AI lines are not available for it.</EmptyState>;
  }

  return (
    <div className="space-y-2 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
      <div className="flex items-center gap-2">
        <Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Find in transcript" aria-label="Find in transcript" className="h-9" />
        {!following && <button type="button" onClick={() => setFollowing(true)} className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-accent hover:bg-accent-soft">Follow playback</button>}
      </div>
      {needle.length >= 2 && <p className="px-1 text-xs text-muted-foreground tabular">{visible.length} matching lines</p>}
      <div
        ref={scroller}
        role="region"
        aria-label="Transcript lines"
        tabIndex={0}
        className="h-[calc(100dvh-4rem-var(--pinned-h)-3rem-8.5rem)] min-h-48 overflow-y-auto overscroll-contain scroll-auto pr-1 lg:h-auto lg:min-h-0 lg:flex-1"
        onWheel={() => setFollowing(false)}
        onTouchMove={() => setFollowing(false)}
        onPointerDown={event => {
          if (event.target === event.currentTarget) setFollowing(false);
        }}
        onKeyDown={event => {
          if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) setFollowing(false);
        }}
        onScroll={event => {
          if (Math.abs(event.currentTarget.scrollTop - followedTop.current) > 1) setFollowing(false);
        }}
      >
        <ol ref={list} className="space-y-0.5">
          {visible.map(segment => (
            <Line
              key={`${segment.start_seconds}-${segment.text.slice(0, 12)}`}
              segment={segment}
              active={segments[current] === segment}
              query={needle}
              onSeek={seconds => { setFollowing(true); onSeek(seconds); }}
              signedIn={signedIn}
              videoId={videoId}
            />
          ))}
        </ol>
      </div>
    </div>
  );
}
