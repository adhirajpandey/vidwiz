import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Download, Library as LibraryIcon } from 'lucide-react';
import { libraryApi } from '../../api';
import type { LibrarySort } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import PageTitle from '../../components/PageTitle';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import Spinner from '../../components/ui/Spinner';
import { downloadText } from '../../lib/download';
import AddVideoForm from './AddVideoForm';
import VideoRow from './VideoRow';
import { useLibrary } from './queries';

const SORTS: { value: LibrarySort; label: string }[] = [
  { value: 'activity_desc', label: 'Recent activity' },
  { value: 'added_desc', label: 'Recently added' },
  { value: 'title_asc', label: 'Title A–Z' },
  { value: 'title_desc', label: 'Title Z–A' },
];

export default function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const sort = (SORTS.find(option => option.value === params.get('sort'))?.value ?? 'activity_desc');
  const page = Math.max(1, Number(params.get('page')) || 1);
  const [filter, setFilter] = useState(params.get('q') ?? '');
  const q = params.get('q') ?? '';
  const library = useLibrary({ q, page, per_page: 20, sort });
  const notify = useNotify();
  const [exporting, setExporting] = useState(false);

  // Filter as the user types, without a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (filter !== q) {
        const next = new URLSearchParams(params);
        if (filter.trim().length >= 2) next.set('q', filter.trim()); else next.delete('q');
        next.delete('page');
        setParams(next, { replace: true });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [filter, q, params, setParams]);

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next);
  };

  const exportAll = async () => {
    setExporting(true);
    try {
      downloadText(await libraryApi.exportLibrary(), 'vidwiz-library.md');
    } catch (cause) {
      notify.error(cause, 'Export failed', 'The library could not be exported.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageTitle title="Library" />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
        <Button size="sm" onClick={() => void exportAll()} disabled={exporting}>
          <Download className="size-3.5" />Export Markdown
        </Button>
      </div>
      <AddVideoForm />
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter by title" aria-label="Filter by title" />
        <select
          value={sort}
          onChange={event => update('sort', event.target.value === 'activity_desc' ? null : event.target.value)}
          aria-label="Sort videos"
          className="h-10 rounded-lg border border-input bg-card px-3 text-sm"
        >
          {SORTS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>

      {library.isPending && <div className="flex justify-center py-10"><Spinner /></div>}
      {library.isError && <ErrorState title="The library did not load" message="Check your connection and try again." onRetry={() => void library.refetch()} />}
      {library.data && library.data.total === 0 && (
        <EmptyState icon={<LibraryIcon className="size-5" />} title={q ? 'No videos match that title' : 'No saved videos yet'}>
          {q ? 'Try a shorter filter, or search inside transcripts from the search bar.' : 'Paste a YouTube link above, or capture a moment while you watch.'}
        </EmptyState>
      )}
      {library.data && library.data.videos.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground tabular">{library.data.total} videos</p>
          <div className="divide-y divide-border rounded-xl border border-border bg-card p-1">
            {library.data.videos.map(video => <VideoRow key={video.video_id} video={video} />)}
          </div>
          {library.data.total_pages > 1 && (
            <div className="flex items-center justify-center gap-3 text-sm">
              <Button size="sm" disabled={page <= 1} onClick={() => update('page', String(page - 1))}>Previous</Button>
              <span className="text-muted-foreground tabular">{page} / {library.data.total_pages}</span>
              <Button size="sm" disabled={page >= library.data.total_pages} onClick={() => update('page', String(page + 1))}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
