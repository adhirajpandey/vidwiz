import { Link, useSearchParams } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Search, Sparkles } from 'lucide-react';
import { searchApi } from '../../api';
import type { SearchResult } from '../../api';
import PageTitle from '../../components/PageTitle';
import SearchForm from '../../components/SearchForm';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import Spinner from '../../components/ui/Spinner';
import Thumbnail from '../../components/ui/Thumbnail';
import TimeChip from '../../components/ui/TimeChip';
import { videoTitle } from '../../lib/format';
import Snippet from './Snippet';
import { resultLink } from './resultLink';

function ResultRow({ result }: { result: SearchResult }) {
  return (
    <li>
      <Link to={resultLink(result)} className="-mx-2 flex gap-4 rounded-[12px] px-2 py-4 hover:bg-muted">
        <Thumbnail videoId={result.video.video_id} className="hidden w-28 self-start sm:block" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 truncate text-sm text-muted-foreground">
              {result.kind === 'moment' ? 'Your moment in ' : 'Transcript of '}
              <span className="font-semibold text-foreground">{videoTitle(result.video.title, result.video.video_id)}</span>
            </p>
            <TimeChip seconds={result.start_seconds} />
          </div>
          <Snippet parts={result.snippet} />
        </div>
      </Link>
    </li>
  );
}

export default function SearchPage() {
  const [params] = useSearchParams();
  const q = (params.get('q') ?? '').trim();
  const search = useInfiniteQuery({
    queryKey: ['search', q],
    queryFn: ({ pageParam }) => searchApi.search(q, { page: pageParam, per_page: 20 }),
    initialPageParam: 1,
    getNextPageParam: last => (last.has_more ? last.page + 1 : undefined),
    enabled: q.length >= 2,
  });

  const askLink = (
    <Link to={`/ask?q=${encodeURIComponent(q)}`} className="inline-flex items-center gap-1.5 text-sm font-medium underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
      <Sparkles className="size-4" />Ask your library instead
    </Link>
  );

  if (q.length < 2) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageTitle title="Search" />
        <SearchForm className="mb-2 md:hidden" />
        <EmptyState icon={<Search className="size-5" />} title="Search what you watched">
          Find your moments and anything said in your saved videos.
        </EmptyState>
      </div>
    );
  }

  const first = search.data?.pages[0];
  const results = search.data?.pages.flatMap(page => page.results) ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageTitle title={[`“${q}”`, 'Search']} />
      <SearchForm className="md:hidden" />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="display text-3xl">Results for “{q}”</h1>
        {askLink}
      </div>
      {search.isPending && <div className="flex justify-center py-10"><Spinner /></div>}
      {search.isError && <ErrorState title="Search failed" message="Check your connection and try again." onRetry={() => void search.refetch()} />}
      {first?.match === 'fuzzy' && (
        <p className="rounded-[10px] bg-surface px-3 py-2 text-sm text-muted-foreground">No exact matches, so these are close spellings.</p>
      )}
      {first?.match === 'none' && (
        <EmptyState icon={<Search className="size-5" />} title="Nothing found">
          Try fewer or different words. Asking your library also finds ideas phrased differently.
        </EmptyState>
      )}
      {results.length > 0 && (
        <ul className="divide-y divide-border border-t border-border">
          {results.map(result => (
            <ResultRow key={result.kind === 'moment' ? `m${result.moment.id}` : `c${result.chunk_id}`} result={result} />
          ))}
        </ul>
      )}
      {search.hasNextPage && (
        <div className="flex justify-center">
          <Button onClick={() => void search.fetchNextPage()} disabled={search.isFetchingNextPage}>
            {search.isFetchingNextPage ? 'Loading…' : 'More results'}
          </Button>
        </div>
      )}
    </div>
  );
}
