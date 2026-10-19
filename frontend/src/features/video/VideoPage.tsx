import { useCallback, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { BookmarkPlus, ExternalLink, FileText, Sparkles, StickyNote } from 'lucide-react';
import { libraryApi } from '../../api';
import { ApiError } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { useSignedIn } from '../../hooks/useSignedIn';
import PageTitle from '../../components/PageTitle';
import YouTubePlayer from '../../components/wiz/YouTubePlayer';
import type { YouTubePlayerHandle } from '../../components/wiz/YouTubePlayer';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { videoTitle, youtubeUrl } from '../../lib/format';
import { isValidVideoId } from '../../lib/videoUtils';
import AskPanel from './AskPanel';
import CaptureBar from './CaptureBar';
import MomentsPanel from './MomentsPanel';
import OverviewPanel from './OverviewPanel';
import TranscriptPanel from './TranscriptPanel';
import { useVideo } from './queries';

type Tab = 'moments' | 'ask' | 'transcript' | 'overview';
const TABS: Tab[] = ['moments', 'ask', 'transcript', 'overview'];

function numberParam(value: string | null): number | null {
  const parsed = value === null ? NaN : Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function Workspace({ videoId }: { videoId: string }) {
  const signedIn = useSignedIn();
  const [params, setParams] = useSearchParams();
  const video = useVideo(videoId);
  const player = useRef<YouTubePlayerHandle>(null);
  const [playhead, setPlayhead] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const notify = useNotify();

  const startAt = numberParam(params.get('t'));
  const highlightId = numberParam(params.get('m'));
  const resumeId = numberParam(params.get('c'));
  const requested = params.get('tab') as Tab | null;
  const defaultTab: Tab = resumeId !== null ? 'ask' : !signedIn ? 'ask' : 'moments';
  const tab: Tab = requested && TABS.includes(requested) ? requested : defaultTab;
  const startedRef = useRef(false);

  const setTab = (next: string) => {
    const nextParams = new URLSearchParams(params);
    nextParams.set('tab', next);
    setParams(nextParams, { replace: true });
  };
  const setConversation = useCallback((id: number | null) => {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (id === null) next.delete('c'); else next.set('c', String(id));
      next.set('tab', 'ask');
      return next;
    }, { replace: true });
  }, [setParams]);

  const seek = useCallback((seconds: number) => player.current?.watch(seconds), []);

  // Deep links start playback once, when the page opens.
  const playerRef = useCallback((handle: YouTubePlayerHandle | null) => {
    player.current = handle;
    if (handle && startAt !== null && !startedRef.current) {
      startedRef.current = true;
      handle.watch(startAt);
    }
  }, [startAt]);

  if (video.isError) {
    const missing = video.error instanceof ApiError && video.error.response.status === 404;
    return missing ? (
      <EmptyState icon={<FileText className="size-5" />} title="This video is not in VidWiz yet" action={
        signedIn ? (
          <Button variant="primary" onClick={async () => {
            try {
              await libraryApi.save(videoId);
              void queryClient.invalidateQueries({ queryKey: ['library'] });
              void video.refetch();
            } catch (cause) {
              notify.error(cause, 'Video not saved', 'The video could not be saved.');
            }
          }}><BookmarkPlus className="size-4" />Save to library</Button>
        ) : (
          <Link to={`/?video=${videoId}`} className="text-sm font-medium text-accent hover:underline">Try it from the home page</Link>
        )
      }>Save it to fetch its transcript and start capturing moments.</EmptyState>
    ) : (
      <ErrorState title="The video did not load" message="Check your connection and try again." onRetry={() => void video.refetch()} />
    );
  }

  const data = video.data;
  const title = data ? videoTitle(data.title ?? data.metadata?.title, videoId) : 'Loading…';

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] xl:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]">
      <PageTitle title={title} />
      <div className="min-w-0 space-y-4 lg:sticky lg:top-20 lg:self-start">
        <YouTubePlayer ref={playerRef} videoId={videoId} onTimeUpdate={setPlayhead} className="overflow-hidden rounded-xl border border-border" />
        <div className="space-y-1">
          <h1 className="text-lg font-semibold leading-snug">{title}</h1>
          <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
            {data?.metadata?.uploader && <span>{data.metadata.uploader}</span>}
            <a href={youtubeUrl(videoId)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">
              YouTube <ExternalLink className="size-3" />
            </a>
          </p>
        </div>
        {signedIn && (
          <CaptureBar
            videoId={videoId}
            currentTime={() => player.current?.currentTime() ?? null}
            onCaptured={() => setTab('moments')}
          />
        )}
      </div>

      <div className="min-w-0">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList aria-label="Video panels" className="sticky top-14 z-10 bg-background">
            {signedIn && <TabsTrigger value="moments"><StickyNote className="size-4" />Moments</TabsTrigger>}
            <TabsTrigger value="ask"><Sparkles className="size-4" />Ask</TabsTrigger>
            <TabsTrigger value="transcript"><FileText className="size-4" />Transcript</TabsTrigger>
            <TabsTrigger value="overview">Overview</TabsTrigger>
          </TabsList>
          {signedIn && (
            <TabsContent value="moments" className="pt-3">
              <MomentsPanel videoId={videoId} onSeek={seek} highlightId={highlightId} />
            </TabsContent>
          )}
          <TabsContent value="ask" className="pt-3" forceMount hidden={tab !== 'ask'}>
            {data && (
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <AskPanel video={data} seek={seek} signedIn={signedIn} resumeId={resumeId} onConversation={setConversation} />
              </div>
            )}
          </TabsContent>
          <TabsContent value="transcript" className="pt-3">
            <TranscriptPanel videoId={videoId} playhead={playhead} onSeek={seek} signedIn={signedIn} />
          </TabsContent>
          <TabsContent value="overview" className="pt-4">
            {data && <OverviewPanel video={data} signedIn={signedIn} onSeek={seek} onAsk={() => setTab('ask')} />}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default function VideoPage() {
  const { videoId = '' } = useParams();
  if (!isValidVideoId(videoId)) {
    return <EmptyState icon={<FileText className="size-5" />} title="That is not a YouTube video link">Check the address and try again.</EmptyState>;
  }
  return <Workspace key={videoId} videoId={videoId} />;
}
