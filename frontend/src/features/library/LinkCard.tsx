import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Plus, RotateCcw } from 'lucide-react';
import { libraryApi } from '../../api';
import { normalizeApiError } from '../../api/errors';
import { formatClock } from '../../lib/format';
import { cn } from '../../lib/utils';
import { linkTime } from './links';
import Button from '../../components/ui/Button';
import VideoRow from './VideoRow';

type LinkState =
  | { kind: 'checking' }
  | { kind: 'in_library'; video: LibraryVideoRow }
  | { kind: 'new' }
  | { kind: 'unknown' }
  | { kind: 'adding'; open: boolean }
  | { kind: 'failed'; open: boolean; message: string; referenceId?: string };
type LibraryVideoRow = Parameters<typeof VideoRow>[0]['video'];

// A failed membership check makes no claim about whether the video is saved.
export default function LinkCard({ link, videoId, onClear, onAdded }: { link: string; videoId: string; onClear: () => void; onAdded: (videoId: string) => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const startAt = linkTime(link);
  const membership = useQuery({ queryKey: ['library', 'link', videoId], queryFn: () => libraryApi.list({ q: videoId, per_page: 1 }) });
  const preview = useQuery({
    queryKey: ['oembed', videoId],
    queryFn: async ({ signal }) => {
      const response = await fetch(`https://www.youtube.com/oembed?format=json&url=${encodeURIComponent(`https://www.youtube.com/watch?v=${videoId}`)}`, { signal });
      return response.ok ? (await response.json() as { title?: string; author_name?: string }) : null;
    },
  });
  const [action, setAction] = useState<{ kind: 'adding'; open: boolean } | { kind: 'failed'; open: boolean; message: string; referenceId?: string } | null>(null);
  // A failed check claims nothing; adding is still safe because saving twice is a no-op.
  const state: LinkState = action ?? (membership.isPending ? { kind: 'checking' } : membership.isError ? { kind: 'unknown' } : membership.data.videos.find(v => v.video_id === videoId) ? { kind: 'in_library', video: membership.data.videos.find(v => v.video_id === videoId)! } : { kind: 'new' });
  const busyRef = useRef(false);
  const target = `/v/${videoId}${startAt !== null ? `?t=${startAt}` : ''}`;
  const at = startAt ? ` at ${formatClock(startAt)}` : '';

  const add = async (open: boolean) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setAction({ kind: 'adding', open });
    try {
      await libraryApi.save(videoId);
      await queryClient.invalidateQueries({ queryKey: ['library'] });
      if (open) navigate(target); else onAdded(videoId);
    } catch (cause) {
      // The same message and reference the app's error toasts show; an expired session is handled by the app instead.
      const error = normalizeApiError(cause, 'The video could not be saved.');
      if (error.handled) return setAction(null);
      setAction({ kind: 'failed', open, message: error.message, referenceId: error.requestId });
    } finally { busyRef.current = false; }
  };

  if (state.kind === 'in_library') {
    return (
      <div className="rounded-[14px] border border-border bg-card px-3 pb-1 pt-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold">Already in your library</p>
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={() => navigate(target)}>Open{at}</Button>
            <Button size="sm" variant="ghost" onClick={onClear}>Clear</Button>
          </div>
        </div>
        <VideoRow video={state.video} to={target} />
      </div>
    );
  }
  const busy = state.kind === 'adding' || state.kind === 'checking';
  return (
    <div className="flex items-center gap-4 rounded-[14px] border border-border bg-card p-3">
      <img src={`https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`} alt="" className="aspect-video w-40 shrink-0 rounded-[9px] object-cover max-sm:w-28" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="line-clamp-2 text-sm font-semibold">{preview.data?.title ?? `youtube.com/watch?v=${videoId}`}</p>
        {state.kind === 'failed' ? (
          // ErrorState's pieces at card size: red title, the message, then the reference.
          <div role="alert" className="space-y-0.5">
            <p className="text-sm font-semibold text-red-600 dark:text-red-400">Video not saved</p>
            <p className="text-xs leading-relaxed text-muted-foreground">{state.message}</p>
            {state.referenceId && <p className="break-all font-mono text-[11px] text-muted-foreground/70">Reference: {state.referenceId}</p>}
          </div>
        ) : (
          <p className="truncate text-xs text-muted-foreground">
            {[preview.data?.author_name, state.kind === 'checking' ? 'Checking your library…' : state.kind === 'unknown' ? 'Couldn’t check your library' : 'Not in your library yet', startAt && `opens at ${formatClock(startAt)}`].filter(Boolean).join(' · ')}
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1.5">
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void add(state.kind === 'failed' ? state.open : true)}>
            {state.kind === 'adding' && state.open ? <Loader2 className="size-3.5 animate-spin" /> : state.kind === 'failed' ? <RotateCcw className="size-3.5" /> : <Plus className="size-3.5" />}
            {state.kind === 'failed' ? 'Try again' : `Add and open${at}`}
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void add(false)} className={cn(state.kind === 'failed' && 'hidden')}>
            {state.kind === 'adding' && !state.open && <Loader2 className="size-3.5 animate-spin" />}Add to library
          </Button>
          <Button size="sm" variant="ghost" disabled={state.kind === 'adding'} onClick={onClear}>Clear</Button>
        </div>
      </div>
    </div>
  );
}
