import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

export interface YouTubePlayerHandle { watch: (seconds: number) => void }
export interface Player {
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  playVideo: () => void;
  getPlayerState: () => number;
  destroy: () => void;
}
export interface PlayerOptions {
  videoId: string;
  playerVars: { origin: string; rel: number; playsinline: number };
  events: {
    onReady: () => void;
    onStateChange: (event: { data: number }) => void;
    onError: () => void;
    onAutoplayBlocked: () => void;
  };
}
type YouTubeAPI = { Player: new (element: HTMLElement, options: PlayerOptions) => Player };
declare global {
  interface Window { YT?: YouTubeAPI; onYouTubeIframeAPIReady?: () => void }
}

let apiPromise: Promise<YouTubeAPI> | undefined;
function loadYouTubeAPI(): Promise<YouTubeAPI> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!apiPromise) {
    apiPromise = new Promise<YouTubeAPI>((resolve, reject) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        try { previous?.(); } finally {
          if (window.YT?.Player) resolve(window.YT);
          else reject(new Error('YouTube player API unavailable'));
        }
      };
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      script.async = true;
      script.onerror = () => { script.remove(); reject(new Error('YouTube player API failed to load')); };
      document.head.appendChild(script);
    }).catch(error => { apiPromise = undefined; throw error; });
  }
  return apiPromise;
}

const YouTubePlayer = forwardRef<YouTubePlayerHandle, { videoId: string }>(function YouTubePlayer({ videoId }, ref) {
  const container = useRef<HTMLDivElement>(null);
  const mount = useRef<HTMLDivElement>(null);
  const watch = useRef<(seconds: number) => void>(() => undefined);
  const [notice, setNotice] = useState<{ message: string; seconds: number } | null>(null);

  useImperativeHandle(ref, () => ({ watch: seconds => watch.current(seconds) }), []);

  useEffect(() => {
    let disposed = false;
    let player: Player | undefined;
    let ready = false;
    let failed = false;
    let pending: number | null = null;
    let lastSeconds = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const clearTimer = () => { if (timer !== undefined) clearTimeout(timer); timer = undefined; };
    const showFailure = (message: string) => {
      if (disposed) return;
      clearTimer();
      pending = null;
      setNotice({ message, seconds: lastSeconds });
    };
    const play = () => {
      if (!ready || !player || pending === null) return;
      const seconds = pending;
      pending = null;
      try {
        player.seekTo(Math.max(0, seconds - 2), true);
        player.playVideo();
        if (player.getPlayerState() === 1) clearTimer();
      } catch {
        showFailure('Playback could not start. Try watching on YouTube.');
      }
    };
    watch.current = seconds => {
      if (disposed || !Number.isFinite(seconds) || seconds < 0) return;
      lastSeconds = seconds;
      pending = seconds;
      setNotice(null);
      clearTimer();
      const bounds = container.current?.getBoundingClientRect();
      if (bounds && (bounds.top < 0 || bounds.bottom > window.innerHeight)) {
        container.current?.scrollIntoView({
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center',
        });
      }
      if (failed) { showFailure('The video player is unavailable. Watch this passage on YouTube.'); return; }
      timer = setTimeout(() => showFailure('Playback did not start. Press Play in the video or open YouTube.'), 10_000);
      play();
    };
    const element = document.createElement('div');
    mount.current?.appendChild(element);
    void loadYouTubeAPI().then(api => {
      if (disposed) return;
      player = new api.Player(element, {
        videoId, playerVars: { origin: window.location.origin, rel: 0, playsinline: 1 },
        events: {
          onReady: () => { if (!disposed) { ready = true; play(); } },
          onStateChange: event => {
            if (!disposed && event.data === 1) { clearTimer(); setNotice(null); }
          },
          onError: () => { failed = true; showFailure('The video player is unavailable. Watch this passage on YouTube.'); },
          onAutoplayBlocked: () => showFailure('Press Play in the video to watch this passage, or open YouTube.'),
        },
      });
    }).catch(() => { failed = true; showFailure('The video player could not load. Watch this passage on YouTube.'); });
    const host = mount.current;
    return () => {
      disposed = true;
      pending = null;
      clearTimer();
      watch.current = () => undefined;
      player?.destroy();
      host?.replaceChildren();
    };
  }, [videoId]);

  return <div ref={container}>
    <div ref={mount} className="aspect-video bg-black [&_iframe]:h-full [&_iframe]:w-full" />
    {notice && <div role="status" className="p-3 text-sm bg-muted text-foreground">
      {notice.message}{' '}
      <a className="underline wiz-accent-text" href={`https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}&t=${Math.max(0, Math.floor(notice.seconds - 2))}s`}
        target="_blank" rel="noopener noreferrer">Open on YouTube</a>
    </div>}
  </div>;
});

export default YouTubePlayer;
