import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { momentsApi } from '../../api';
import Button from '../../components/ui/Button';
import ErrorState from '../../components/ui/ErrorState';
import Spinner from '../../components/ui/Spinner';
import Thumbnail from '../../components/ui/Thumbnail';
import { videoTitle } from '../../lib/format';
import MomentItem from '../moments/MomentItem';
import { hasPendingWork, momentKeys } from '../moments/queries';
import { groupFeed } from './groupFeed';


export default function MomentFeed() {
  const feed = useInfiniteQuery({
    queryKey: momentKeys.feed,
    queryFn: ({ pageParam }) => momentsApi.feed(pageParam, 20),
    initialPageParam: 1,
    getNextPageParam: last => (last.has_more ? last.page + 1 : undefined),
    refetchInterval: query =>
      hasPendingWork(query.state.data?.pages.flatMap(page => page.moments)) ? 5000 : false,
  });

  if (feed.isPending) return <div className="flex justify-center py-10"><Spinner /></div>;
  if (feed.isError) return <ErrorState title="Recent moments did not load" message="Check your connection and try again." onRetry={() => void feed.refetch()} />;

  const moments = feed.data.pages.flatMap(page => page.moments);
  if (!moments.length) return null;
  const groups = groupFeed(moments);

  return (
    <section aria-labelledby="recent-moments">
      <h2 id="recent-moments" className="mb-3 text-sm font-semibold text-muted-foreground">Recent moments</h2>
      <div className="space-y-6">
        {groups.map((group, index) => (
          <Fragment key={group.key}>
            {(index === 0 || groups[index - 1].day !== group.day) && (
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{group.day}</h3>
            )}
            <div className="rounded-xl border border-border bg-card p-3">
              {group.videoId && (
                <Link to={`/v/${group.videoId}`} className="mb-1 flex items-center gap-3 rounded-lg p-1 hover:bg-muted">
                  <Thumbnail videoId={group.videoId} className="w-20" />
                  <span className="line-clamp-2 text-sm font-medium">{videoTitle(group.title, group.videoId)}</span>
                </Link>
              )}
              <ul className="divide-y divide-border">
                {group.moments.map(moment => <MomentItem key={moment.id} moment={moment} showQuote={false} />)}
              </ul>
            </div>
          </Fragment>
        ))}
      </div>
      {feed.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button onClick={() => void feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
            {feed.isFetchingNextPage ? 'Loading…' : 'Load more'}
          </Button>
        </div>
      )}
    </section>
  );
}
