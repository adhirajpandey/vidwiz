import { useEffect, useLayoutEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Download, Library as LibraryIcon, Search } from 'lucide-react';
import { libraryApi } from '../../api';
import type { LibrarySort, LibraryView } from '../../api';
import { useArrival, useArrivalTint } from '../../hooks/useArrival';
import type { Arrival } from '../../hooks/useArrival';
import { useNotify } from '../../hooks/useNotify';
import PageTitle from '../../components/PageTitle';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import { Tooltip } from '../../components/ui/Tooltip';
import Spinner from '../../components/ui/Spinner';
import { downloadText } from '../../lib/download';
import { extractVideoId } from '../../lib/videoUtils';
import { cn } from '../../lib/utils';
import LinkCard from './LinkCard';
import SortMenu from './SortMenu';
import VideoRow from './VideoRow';
import { looksLikeLink } from './links';
import { useLibrary } from './queries';

const SORTS: LibrarySort[] = ['activity_desc', 'added_desc', 'moments_desc', 'chats_desc', 'title_asc', 'title_desc'];
const VIEWS: { value: LibraryView; label: string }[] = [{ value: 'all', label: 'All' }, { value: 'with_moments', label: 'With moments' }, { value: 'with_chats', label: 'With chats' }];

/** The video just added: its tint fades once it is shown; the label stays. */
function JustAdded({ arrival, onShown, children }: { arrival: Arrival<string>; onShown: (key: number) => void; children: ReactNode }) {
  useLayoutEffect(() => { if (arrival.shownAt === null) onShown(arrival.key); }, [arrival, onShown]);
  const tint = useArrivalTint(arrival.shownAt);
  return <div style={tint.style} className={cn('-mx-2 rounded-[12px] px-2', tint.className)}><p className="pt-2 text-xs font-semibold">Added just now</p>{children}</div>;
}

export default function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const sort = SORTS.find(s => s === params.get('sort')) ?? 'activity_desc';
  const view = VIEWS.find(v => v.value === params.get('view'))?.value ?? 'all';
  const page = Math.max(1, Math.floor(Number(params.get('page')) || 1));
  const q = params.get('q') ?? '';
  const [input, setInput] = useState({ query: q, value: q });
  if (input.query !== q) setInput({ query: q, value: input.value.trim() === q ? input.value : q });
  const filter = input.value;
  const link = looksLikeLink(filter) ? filter.trim() : null;
  const pasted = link ? extractVideoId(link) : null;
  const library = useLibrary({ q, page, per_page: 20, sort, view });
  const notify = useNotify();
  const [exporting, setExporting] = useState(false);
  const { arrival: justAdded, arrive, shown } = useArrival<string>(null);

  useEffect(() => {
    if (link) return;
    const timer = setTimeout(() => {
      const trimmed = filter.trim().length >= 2 ? filter.trim() : '';
      if (trimmed === q) return;
      const next = new URLSearchParams(params);
      if (trimmed) next.set('q', trimmed); else next.delete('q');
      next.delete('page');
      setParams(next, { replace: true });
    }, 300);
    return () => clearTimeout(timer);
  }, [filter, link, q, params, setParams]);

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    if (key !== 'page') next.delete('page');
    setParams(next);
  };
  const clear = () => { setInput({ query: '', value: '' }); const next = new URLSearchParams(params); next.delete('q'); next.delete('page'); setParams(next); };
  const exportAll = async () => {
    setExporting(true);
    try { downloadText(await libraryApi.exportLibrary(), 'vidwiz-library.md'); }
    catch (cause) { notify.error(cause, 'Export failed', 'The library could not be exported.'); }
    finally { setExporting(false); }
  };
  const total = library.data?.total;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="Library" />
      <div className="flex items-end justify-between gap-3">
        <div><h1 className="display text-4xl">Library</h1>{total !== undefined && !link && <p className="mt-1 cursor-default text-sm text-muted-foreground tabular">{q ? `${total} videos match “${q}”` : `${total} videos`}</p>}</div>
        <Tooltip label="Export Markdown"><Button size="sm" variant="ghost" aria-label="Export Markdown" onClick={() => void exportAll()} disabled={exporting}><Download className="size-4" /><span className="hidden sm:inline">Export</span></Button></Tooltip>
      </div>
      <div className="flex gap-2">
        <label className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={filter} onChange={event => setInput({ query: q, value: event.target.value })} aria-invalid={Boolean(link && !pasted)} className={cn('pl-9', link && !pasted && 'border-destructive/60 focus:border-destructive/70')} placeholder="Search or paste a link" aria-label="Search titles and channels, or paste a link" />
        </label>
        <SortMenu sort={sort} onChange={value => update('sort', value)} />
      </div>
      {!link && <div role="group" aria-label="Library views" className="-mx-4 flex gap-1 overflow-x-auto border-b border-border px-4 sm:mx-0 sm:px-0">
        {VIEWS.map(v => <button key={v.value} type="button" aria-pressed={view === v.value} onClick={() => update('view', v.value)} className={cn('-mb-px shrink-0 border-b-2 px-3 pb-2 pt-1 text-sm font-semibold', view === v.value ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>{v.label} <span className="ml-0.5 text-xs font-medium text-muted-foreground tabular">{library.data?.counts[v.value] ?? '…'}</span></button>)}
      </div>}
      {link && !pasted ? <p role="alert" className="-mt-3 text-xs text-destructive">Paste a YouTube video link, like youtube.com/watch?v=… or youtu.be/…</p>
        : pasted && link ? <LinkCard key={pasted} link={link} videoId={pasted} onClear={clear} onAdded={id => { arrive(id); setInput({ query: '', value: '' }); setParams({ sort: 'activity_desc' }); }} />
        : <>
          {library.isPending && <div className="flex justify-center py-10"><Spinner /></div>}
          {library.isError && <ErrorState title="The library did not load" message="Check your connection and try again." onRetry={() => void library.refetch()} />}
          {library.data && total === 0 && <EmptyState icon={<LibraryIcon className="size-5" />} title={q ? 'No titles or channels match' : view === 'all' ? 'No saved videos yet' : 'No videos in this view'}>{q ? 'Try a shorter search, or search inside transcripts from the search bar.' : 'Paste a YouTube link above, or capture a moment while you watch.'}</EmptyState>}
          {library.data && <div className="divide-y divide-border/70" aria-busy={library.isFetching}>
            {library.data.videos.map(video => video.video_id === justAdded?.target ? <JustAdded key={video.video_id} arrival={justAdded} onShown={shown}><VideoRow video={video} /></JustAdded> : <VideoRow key={video.video_id} video={video} />)}
          </div>}
          {library.data && library.data.total_pages > 1 && <div className="flex items-center justify-between gap-3 text-sm">
            <Button disabled={page <= 1 || library.isPlaceholderData} onClick={() => update('page', String(page - 1))}>Previous</Button>
            <span className="text-muted-foreground">Page {page} of {library.data.total_pages}</span>
            <Button disabled={page >= library.data.total_pages || library.isPlaceholderData} onClick={() => update('page', String(page + 1))}>Next</Button>
          </div>}
        </>}
    </div>
  );
}
