import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Shuffle, Sparkles, StickyNote } from 'lucide-react';
import { momentsApi } from '../../api';
import TimeChip from '../../components/ui/TimeChip';
import Thumbnail from '../../components/ui/Thumbnail';
import ErrorState from '../../components/ui/ErrorState';
import { formatRelative, videoTitle } from '../../lib/format';
import { playFrom } from '../moments/queries';

export default function Resurface() {
  const [skip, setSkip] = useState(0);
  const query = useQuery({
    queryKey: ['moments', 'resurface', skip],
    queryFn: async () => {
      const result = await momentsApi.resurface(skip);
      if (result.state === 'none' && skip > 0) return { result: await momentsApi.resurface(0), nextSkip: 1 };
      return { result, nextSkip: skip + 1 };
    },
    placeholderData: previous => previous,
    refetchInterval: 60_000,
  });
  if (query.isError) return <ErrorState compact title="Older moments did not load" message="Try again to see a moment from your library." onRetry={() => void query.refetch()} />;
  if (query.data?.result.state !== 'found') return null;
  const row = query.data.result.moment;
  // This legacy batch records its import day rather than the original capture date.
  const imported = row.source === 'legacy' && row.created_at.startsWith('2025-08-03');
  const savedLabel = imported ? 'from before Aug 2025' : `saved ${formatRelative(row.created_at)}`;
  const KindIcon = row.ai_text ? Sparkles : row.note ? StickyNote : null;
  return (
    <section aria-labelledby="resurface">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="resurface" className="display text-xl">From your library</h2>
        <button type="button" onClick={() => setSkip(query.data?.nextSkip ?? 0)} disabled={query.isFetching} aria-label="Another moment" className="inline-flex items-center gap-1.5 disabled:opacity-50 text-sm font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
          <Shuffle className="size-3.5" />Another
        </button>
      </div>
      <div key={row.id} className="rounded-[14px] border border-border bg-card px-4 py-4">
        <p className="flex gap-2.5 text-lg font-medium leading-7">
          {KindIcon && <KindIcon className="mt-1.5 size-4 shrink-0 text-muted-foreground" aria-label={row.ai_text ? 'AI line' : 'Your note'} />}
          <Link to={`/v/${row.video_id}?t=${playFrom(row)}&m=${row.id}`} className="hover:underline">{row.ai_text?.trim() || row.note?.trim() || row.quote?.trim()}</Link>
        </p>
        {row.ai_text && row.note && <p className="mt-2 border-l-2 border-foreground/25 pl-3 text-sm leading-6">{row.note}</p>}
        <div className="mt-3 border-t border-border pt-2">
          <Link to={`/v/${row.video_id}?t=${playFrom(row)}&m=${row.id}`} className="-mx-1 -mb-1 flex items-center gap-3 rounded-[10px] p-1 hover:bg-muted">
            <Thumbnail videoId={row.video_id!} className="w-20" />
            <span className="min-w-0 flex-1">
              <span className="line-clamp-1 text-[15px] font-semibold leading-snug">{videoTitle(row.video_title, row.video_id!)}</span>
              <span className="flex min-w-0 gap-1 text-xs text-muted-foreground">
                {row.video_metadata?.uploader && <span className="truncate">{row.video_metadata?.uploader}</span>}
                <span className="shrink-0">{row.video_metadata?.uploader && '· '}{savedLabel}</span>
              </span>
            </span>
            <TimeChip seconds={row.at_seconds} />
          </Link>
        </div>
      </div>
    </section>
  );
}

