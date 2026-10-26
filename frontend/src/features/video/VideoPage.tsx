import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { CSSProperties } from 'react';
import { Link, useLocation, useNavigationType, useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { BookmarkPlus, ExternalLink, FileText, Sparkles, StickyNote } from 'lucide-react';
import { libraryApi } from '../../api';
import { ApiError } from '../../api';
import { useArrival } from '../../hooks/useArrival';
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
import MomentStrip from './MomentStrip';
import MomentsPanel from './MomentsPanel';
import OverviewPanel from './OverviewPanel';
import TranscriptPanel from './TranscriptPanel';
import { useVideo } from './queries';

type Tab = 'moments' | 'ask' | 'transcript' | 'overview';
const TABS: Tab[] = ['moments', 'ask', 'transcript', 'overview'];
const TAB_LABELS: Record<Tab, string> = { moments: 'Moments', ask: 'Ask', transcript: 'Transcript', overview: 'Overview' };

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
  // A moment link, a back or forward step to one, or View moment is an arrival; changing panels is not.
  const { arrival, arrive, shown } = useArrival(highlightId);
  const location = useLocation();
  const navigationType = useNavigationType();
  const [seenLocation, setSeenLocation] = useState(location.key);
  if (seenLocation !== location.key) {
    setSeenLocation(location.key);
    if (navigationType !== 'REPLACE' && highlightId !== null) arrive(highlightId);
  }
  const resumeId = numberParam(params.get('c'));
  const requested = params.get('tab') as Tab | null;
  const defaultTab: Tab = resumeId !== null ? 'ask' : !signedIn ? 'ask' : 'moments';
  const tab: Tab = requested && TABS.includes(requested) ? requested : defaultTab;
  const [askOpened, setAskOpened] = useState(tab === 'ask');
  useEffect(() => { if (tab === 'ask') setAskOpened(true); }, [tab]);
  const pinned = useRef<HTMLDivElement>(null);
  const [pinnedHeight, setPinnedHeight] = useState(0);
  useEffect(() => {
    // Phones: the tab bar pins right under the player block, whose height changes with notices.
    const node = pinned.current;
    if (!node) return;
    const observer = new ResizeObserver(() => setPinnedHeight(node.offsetHeight));
    observer.observe(node);
    return () => observer.disconnect();
  }, [video.isError]);
  const wideScreen = useSyncExternalStore(
    listener => { const query = window.matchMedia('(min-width: 1024px)'); query.addEventListener('change', listener); return () => query.removeEventListener('change', listener); },
    () => window.matchMedia('(min-width: 1024px)').matches,
  );
  const sideTab: Tab = wideScreen && tab === 'moments' ? 'transcript' : tab;

  const [askDraft, setAskDraft] = useState<{ text: string; id: number } | null>(null);
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
      next.set('tab', tab);
      return next;
    }, { replace: true });
  }, [setParams, tab]);

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
    return <><PageTitle title="Video" />{missing ? (
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
          <Link to={`/?video=${videoId}`} className="text-sm font-medium underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">Try it from the home page</Link>
        )
      }>Save it to fetch its transcript and start capturing moments.</EmptyState>
    ) : (
      <ErrorState title="The video did not load" message="Check your connection and try again." onRetry={() => void video.refetch()} />
    )}</>;
  }

  const data = video.data;
  const title = data ? videoTitle(data.title ?? data.metadata?.title, videoId) : 'Loading…';
  // The tab title never shows the raw video ID that `videoTitle` falls back to.
  const tabTitle = data ? [(data.title ?? data.metadata?.title)?.trim() || 'Video', TAB_LABELS[sideTab]] : 'Video';

  const playerEl = <YouTubePlayer ref={playerRef} videoId={videoId} onTimeUpdate={setPlayhead} className="overflow-hidden rounded-[14px] shadow-[0_24px_60px_rgb(10_12_40/0.18)]" />;
  const stripEl = signedIn && data?.metadata?.duration ? <MomentStrip videoId={videoId} duration={data.metadata.duration} playhead={playhead} onSeek={seek} /> : null;
  const titleEl = (
    <div className="space-y-1">
      <h1 className="display text-2xl">{title}</h1>
      <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
        {data?.metadata?.uploader && <span>{data.metadata.uploader}</span>}
        <a href={youtubeUrl(videoId)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">
          YouTube <ExternalLink className="size-3" />
        </a>
      </p>
    </div>
  );
  const captureEl = signedIn && (
    <CaptureBar
      videoId={videoId}
      currentTime={() => player.current?.currentTime() ?? null}
      playhead={playhead}
      onView={id => {
        arrive(id);
        setParams(previous => {
          const next = new URLSearchParams(previous);
          if (!wideScreen) next.set('tab', 'moments');
          next.set('m', String(id));
          next.delete('t');
          return next;
        }, { replace: true });
      }}
    />
  );
  const pane = 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain lg:pr-1';
  const panels = (
    <Tabs value={sideTab} onValueChange={setTab} className="lg:flex lg:h-full lg:min-h-0 lg:flex-col">
      <TabsList aria-label="Video panels" className="video-tabs z-10 bg-background max-lg:sticky max-lg:top-[calc(4rem+var(--pinned-h))] lg:shrink-0">
        {signedIn && <TabsTrigger value="moments" className="lg:hidden"><StickyNote className="size-4" />Moments</TabsTrigger>}
        <TabsTrigger value="ask"><Sparkles className="size-4" />Ask</TabsTrigger>
        <TabsTrigger value="transcript"><FileText className="size-4" />Transcript</TabsTrigger>
        <TabsTrigger value="overview">Overview</TabsTrigger>
      </TabsList>
      {signedIn && (
        <TabsContent value="moments" className={`pt-3 ${pane}`}>
          <MomentsPanel videoId={videoId} onSeek={seek} arrival={arrival} onArrivalShown={shown} />
        </TabsContent>
      )}
      <TabsContent value="ask" className="pt-3 hidden:!hidden lg:flex lg:min-h-0 lg:flex-1 lg:flex-col" forceMount hidden={sideTab !== 'ask'}>
        {data && (sideTab === 'ask' || askOpened) && (
          <div className="overflow-hidden rounded-[14px] border border-border bg-card lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
            <AskPanel video={data} seek={seek} signedIn={signedIn} resumeId={resumeId} onConversation={setConversation} draft={askDraft} />
          </div>
        )}
      </TabsContent>
      <TabsContent value="transcript" className="pt-3 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
        <TranscriptPanel videoId={videoId} playhead={playhead} onSeek={seek} signedIn={signedIn} />
      </TabsContent>
      <TabsContent value="overview" className={`pt-4 ${pane}`}>
        {data && <OverviewPanel video={data} signedIn={signedIn} onSeek={seek} onAsk={question => { setAskDraft(previous => ({ text: question, id: (previous?.id ?? 0) + 1 })); setTab('ask'); }} />}
      </TabsContent>
    </Tabs>
  );

  // Wide screens: the workspace fills the window and each column scrolls on its own; the page itself does not scroll.
  // Phones: the player, its moment strip, and the save bar pin under the header; the tab bar pins under them.
  return (
    <div style={{ '--pinned-h': `${pinnedHeight}px` } as CSSProperties}
      className="video-workspace grid gap-4 lg:h-[calc(100dvh-9rem)] lg:min-h-[36rem] lg:gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] xl:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]">
      <PageTitle title={tabTitle} />
      <div className="video-left max-lg:contents lg:flex lg:min-h-0 lg:flex-col lg:gap-4">
        <div ref={pinned} className="video-pinned max-lg:sticky max-lg:top-16 max-lg:z-20 max-lg:-mx-4 max-lg:space-y-4 max-lg:bg-background max-lg:px-4 max-lg:pb-2 lg:contents">
          <div className="lg:order-1 lg:shrink-0">{playerEl}</div>
          {stripEl && <div className="lg:order-2 lg:shrink-0">{stripEl}</div>}
          {captureEl && <div className="lg:order-4 lg:shrink-0">{captureEl}</div>}
        </div>
        <div className="lg:order-3 lg:shrink-0">{titleEl}</div>
        {signedIn && wideScreen && (
          <section aria-label="Your moments" className="video-moments hidden border-t border-border/70 pt-3 lg:order-5 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
            <div data-pane="moments" className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-2">
              <MomentsPanel videoId={videoId} onSeek={seek} arrival={arrival} onArrivalShown={shown} />
            </div>
          </section>
        )}
      </div>
      <div className="min-w-0 lg:flex lg:min-h-0 lg:flex-col">{panels}</div>
    </div>
  );
}

export default function VideoPage() {
  const { videoId = '' } = useParams();
  if (!isValidVideoId(videoId)) {
    return <><PageTitle title="Video" /><EmptyState icon={<FileText className="size-5" />} title="That is not a YouTube video link">Check the address and try again.</EmptyState></>;
  }
  return <Workspace key={videoId} videoId={videoId} />;
}
