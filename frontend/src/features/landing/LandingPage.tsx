import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Helmet } from 'react-helmet-async';
import { DESKTOP_MEDIA, EMPTY_POSTER, MOBILE_MEDIA, mediaUrl } from './media';
import { Link, useNavigate } from 'react-router-dom';
import { conversationsApi } from '../../api';
import config from '../../config';
import { useHydrated } from '../../hooks/useHydrated';
import { useNotify } from '../../hooks/useNotify';
import { formatClock } from '../../lib/format';
import { LANDING_TITLE } from '../../lib/title';
import { extractStartSeconds, extractVideoId } from '../../lib/videoUtils';
import Seo from '../../components/Seo';
import './landing.css';

// Every recording and answer on this page is real: the demo account's library,
// recorded on vidwiz.online. Phones get the phone recordings; CSS hides the other frame.
const prefersReducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

type Source = { videoId: string; at: number; title: string; short: string };
const SOURCES: Record<'links' | 'essays' | 'feynman', Source> = {
  links: { videoId: 'ziE6UExsOrs', at: 977, title: 'Zettelkasten Smart Notes: Step by Step with Obsidian', short: 'Zettelkasten Smart Notes' },
  essays: { videoId: 'N4YjXJVzoZY', at: 275, title: 'Mini Essays: The Ultimate Learning Tool', short: 'Mini Essays' },
  feynman: { videoId: 'N4YjXJVzoZY', at: 139, title: 'Mini Essays: The Ultimate Learning Tool', short: 'Mini Essays' },
};

type Cue = { from: number; to?: number; name: string };
const NO_CUES: Cue[] = [];

// The extension recordings open on fullscreen YouTube: Alt+S lands at about 1.8s and the toast at 2s.
const SHORTCUT_CUES: Cue[] = [
  { from: 1.35, to: 2.65, name: 'keys' },
  { from: 1.75, to: 2.2, name: 'pressed' },
  { from: 2.05, name: 'zoomed' },
];
const KEY_CUES = SHORTCUT_CUES.slice(0, 2);
// The same save, then the extension's popup with the moment from 5s.
const EXTENSION_CUES: Cue[] = [...KEY_CUES, { from: 2.05, to: 4.1, name: 'zoomed' }];
const KEYS = <span className="keys" aria-hidden="true"><ModKey /><i>+</i><kbd>S</kbd></span>;

/** Alt, or Option on a Mac. The prerendered page says Alt until it hydrates. */
function ModKey() {
  const hydrated = useHydrated();
  return <kbd>{hydrated && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌥' : 'Alt'}</kbd>;
}

type Place = 'computer' | 'phone' | 'web';
const WAYS: { key: Place; title: string; tab: string; body: ReactNode; icon: ReactNode }[] = [
  {
    key: 'computer',
    title: 'On your computer',
    tab: 'Computer',
    body: <>Press <span className="combo"><ModKey /><i aria-hidden="true">+</i><kbd>S</kbd></span> on any YouTube video, even in fullscreen, with the Chrome extension.</>,
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2.5" y="4" width="19" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></svg>,
  },
  {
    key: 'phone',
    title: 'On your phone',
    tab: 'Phone',
    body: 'Share a video to VidWiz, or save the moment with a phone shortcut.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="6" y="2.5" width="12" height="19" rx="2.5" /><path d="M11 18.5h2" /></svg>,
  },
  {
    key: 'web',
    title: 'On the web',
    tab: 'Web',
    body: 'Paste a link into VidWiz and save from the player or the transcript.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>,
  },
];

/** Fires once when the element first comes into view. */
function useSeenOnce<T extends Element>(threshold = 0.2) {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || seen) return;
    if (typeof IntersectionObserver === 'undefined') { setSeen(true); return; }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setSeen(true); observer.disconnect(); }
    }, { threshold, rootMargin: '0px 0px -8% 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

function Reveal({ as: Tag = 'div', delay = 0, className = '', children, ...rest }: {
  as?: 'div' | 'p' | 'h1' | 'h2'; delay?: 0 | 1 | 2 | 3; className?: string; children: ReactNode; id?: string;
}) {
  const [ref, seen] = useSeenOnce<HTMLElement>();
  return (
    <Tag ref={ref as never} className={`rv${delay ? ` d${delay}` : ''}${seen ? ' in' : ''} ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}

const PLAY = <svg viewBox="0 0 14 16" fill="currentColor" aria-hidden="true"><path d="M1 0l13 8-13 8z" /></svg>;
const PAUSE = <svg viewBox="0 0 14 16" fill="currentColor" aria-hidden="true"><rect width="4.5" height="16" rx="1" /><rect x="9.5" width="4.5" height="16" rx="1" /></svg>;

/**
 * A recording that loads after initial content, plays muted while visible and
 * pauses when it leaves. Tapping pauses or resumes it. With reduced motion it waits for a tap.
 */
function Clip({ name, ratio, label, cues = NO_CUES, children, media, priority = false }: { name: string; ratio: string; label: string; cues?: Cue[]; children?: ReactNode; media?: string; priority?: boolean }) {
  const screen = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const bar = useRef<HTMLElement>(null);
  const held = useRef(false);
  const [paused, setPaused] = useState(true);
  const [started, setStarted] = useState(false);
  const [playBlocked, setPlayBlocked] = useState(false);
  const [flash, setFlash] = useState<{ key: number; playing: boolean } | null>(null);

  useEffect(() => {
    const node = video.current;
    const box = screen.current;
    if (!node || !box) return;
    let visible = false;
    let ready = false;
    let stopped = false;
    let firstFrame = 0;
    let secondFrame = 0;
    const playIfReady = () => {
      if (!ready || !visible || document.hidden || held.current || prefersReducedMotion()) return;
      // Set the property as well as the attribute for Safari's autoplay policy.
      node.muted = true;
      if (!node.getAttribute('src')) node.src = mediaUrl(name, 'mp4');
      node.play().catch(() => { if (!stopped) setPlayBlocked(true); });
    };
    const afterLoad = () => {
      void Promise.resolve(document.fonts?.ready).then(() => {
        if (stopped) return;
        // Let the loaded poster and text paint before starting a competing video request.
        firstFrame = requestAnimationFrame(() => {
          secondFrame = requestAnimationFrame(() => { ready = true; playIfReady(); });
        });
      });
    };
    if (document.readyState === 'complete') afterLoad();
    else window.addEventListener('load', afterLoad, { once: true });
    const onVisibility = () => { if (document.hidden) node.pause(); else playIfReady(); };
    document.addEventListener('visibilitychange', onVisibility);
    const observer = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting && entry.intersectionRatio >= 0.35;
      if (visible) playIfReady(); else node.pause();
    }, { threshold: [0, 0.35] });
    // Watch the frame, not the video: the zoom cue scales the video past the frame, which would
    // drop its visible share below the threshold and pause it.
    const checkVisibility = () => {
      const rect = box.getBoundingClientRect();
      const width = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0));
      const height = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
      visible = rect.width > 0 && rect.height > 0 && width * height / (rect.width * rect.height) >= 0.35;
      if (visible) playIfReady(); else node.pause();
    };
    if (observer) observer.observe(box);
    else {
      checkVisibility();
      window.addEventListener('scroll', checkVisibility, { passive: true });
      window.addEventListener('resize', checkVisibility);
    }
    let frame = 0;
    const tick = () => {
      const t = node.currentTime;
      if (bar.current && node.duration) bar.current.style.transform = `scaleX(${t / node.duration})`;
      // Cues follow the recording's own clock, so overlays stay in step through pauses and loops.
      // They are data attributes, which React leaves alone when it re-renders the class list.
      for (const cue of cues) screen.current?.toggleAttribute(`data-${cue.name}`, t >= cue.from && (cue.to === undefined || t < cue.to));
      frame = requestAnimationFrame(tick);
    };
    const onPlay = () => { setPaused(false); cancelAnimationFrame(frame); tick(); };
    const onPlaying = () => { setStarted(true); setPlayBlocked(false); };
    const onPause = () => { setPaused(true); cancelAnimationFrame(frame); };
    node.addEventListener('play', onPlay);
    node.addEventListener('playing', onPlaying);
    node.addEventListener('pause', onPause);
    return () => {
      stopped = true;
      window.removeEventListener('load', afterLoad);
      document.removeEventListener('visibilitychange', onVisibility);
      cancelAnimationFrame(firstFrame);
      cancelAnimationFrame(secondFrame);
      node.pause();
      observer?.disconnect();
      window.removeEventListener('scroll', checkVisibility);
      window.removeEventListener('resize', checkVisibility);
      cancelAnimationFrame(frame);
      node.removeEventListener('play', onPlay);
      node.removeEventListener('playing', onPlaying);
      node.removeEventListener('pause', onPause);
    };
  }, [name, cues]);

  const toggle = () => {
    const node = video.current;
    if (!node) return;
    node.muted = true;
    if (!node.getAttribute('src')) node.src = mediaUrl(name, 'mp4');
    const willPlay = node.paused;
    held.current = !willPlay;
    if (willPlay) node.play().catch(() => setPlayBlocked(true)); else node.pause();
    setFlash({ key: Date.now(), playing: willPlay });
  };

  return (
    <div
      ref={screen}
      className={`screen${paused ? ' paused' : ''}${playBlocked ? ' play-blocked' : ''}`}
      style={{ aspectRatio: ratio }}
      role="button"
      tabIndex={0}
      aria-label={`${label} Press to ${paused ? 'play' : 'pause'}.`}
      onClick={toggle}
      onKeyDown={event => { if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); toggle(); } }}
    >
      <video ref={video} muted loop playsInline preload="none" aria-hidden="true" />
      <picture className={`clip-poster${started ? ' played' : ''}`}>
        <source media={media} srcSet={mediaUrl(name, 'webp')} type="image/webp" />
        <img src={EMPTY_POSTER} alt="" loading={priority ? 'eager' : 'lazy'} fetchPriority={priority ? 'high' : 'auto'} />
      </picture>
      {children}
      <span className="prog" aria-hidden="true"><i ref={bar} /></span>
      {flash && <span key={flash.key} className="flash go" aria-hidden="true">{flash.playing ? PLAY : PAUSE}</span>}
      <span className="playbadge" aria-hidden="true">{PLAY}</span>
    </div>
  );
}

function Browser({ url, children }: { url: string; children: ReactNode }) {
  return (
    <figure className="browser">
      <div className="chrome" aria-hidden="true">
        <i /><i /><i />
        <span><svg viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="8" rx="2" fill="currentColor" /><path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" strokeWidth="1.8" /></svg>{url}</span>
      </div>
      {children}
    </figure>
  );
}

/** A frame for recordings that already show the real browser toolbar. */
function Window({ children }: { children: ReactNode }) {
  return <figure className="browser bare">{children}</figure>;
}

function Phone({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <figure className={`phone ${className}`.trim()}>{children}</figure>;
}

const CHROME_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <circle cx="12" cy="12" r="9.5" /><circle cx="12" cy="12" r="3.6" /><path d="M12 8.4h8.6M8.9 13.8 4.6 6.4M15.1 13.8l-4.3 7.6" />
  </svg>
);
const SPARKLE = (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M10 2.5l1.7 4.8 4.8 1.7-4.8 1.7L10 15.5l-1.7-4.8L3.5 9l4.8-1.7zM18 13l.9 2.6 2.6.9-2.6.9L18 20l-.9-2.6-2.6-.9 2.6-.9z" />
  </svg>
);
const CHECK = <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 10.5l4 4 8-9" /></svg>;

function Eyebrow({ n, children }: { n: string; children: ReactNode }) {
  return <p className="eyebrow"><b>{n}</b> {children}</p>;
}

function Cite({ source, onOpen }: { source: Source; onOpen: (source: Source) => void }) {
  return (
    <button type="button" className="cite" onClick={() => onOpen(source)}>
      <span className="t"><svg viewBox="0 0 10 12" fill="currentColor" aria-hidden="true"><path d="M0 0l10 6-10 6z" /></svg>{formatClock(source.at)}</span>
      {source.short}
    </button>
  );
}

/** A real answer from Ask; the lines arrive one by one the first time it is on screen. */
function AskCard({ onOpen }: { onOpen: (source: Source) => void }) {
  const hydrated = useHydrated();
  const [ref, seen] = useSeenOnce<HTMLDivElement>(0.35);
  const step = (index: number, className = '') => ({ className: `step ${className}`.trim(), style: { transitionDelay: hydrated && prefersReducedMotion() ? '0s' : `${0.15 + index * 0.32}s` } });
  return (
    <div ref={ref} className={`ask${seen ? ' go' : ''}`} role="group" aria-label="An answer from Ask, with its sources">
      <div className="ask-head">{SPARKLE}Ask your library</div>
      <div className="ask-body">
        <p {...step(0, 'q')}>My notes never stick. What do my videos say I should do differently?</p>
        <div className="a">
          <div {...step(1, 'who')}>{SPARKLE}From two videos in your library</div>
          <p {...step(2)}><strong>Write to test what you understand.</strong> Writing your notes out shows you the links and the gaps in what you know.<br /><Cite source={SOURCES.links} onOpen={onOpen} /></p>
          <p {...step(3)}><strong>Turn ideas into mini essays.</strong> Putting an idea into your own words forces you to think, and exposes what you haven't understood yet.<br /><Cite source={SOURCES.essays} onOpen={onOpen} /></p>
          <p {...step(4)}><strong>Explain it back.</strong> Teaching what you read, the Feynman technique, helps you remember it and use it.<br /><Cite source={SOURCES.feynman} onOpen={onOpen} /></p>
        </div>
      </div>
    </div>
  );
}

/** Plays a cited source from the cited second. */
function SourceDialog({ source, onClose }: { source: Source | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (!node) return;
    if (source && !node.open) node.showModal?.();
    if (!source && node.open) node.close();
  }, [source]);
  return (
    <dialog ref={dialog} className="source" aria-labelledby="source-title" onClose={onClose} onClick={event => { if (event.target === dialog.current) onClose(); }}>
      {source && (
        <>
          <div className="dlg-video">
            <iframe
              title="Source video"
              src={`https://www.youtube-nocookie.com/embed/${source.videoId}?start=${source.at}&autoplay=1&rel=0&playsinline=1`}
              allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
              allowFullScreen
            />
          </div>
          <div className="dlg-bar">
            <span className="t">{formatClock(source.at)}</span>
            <span className="title" id="source-title">{source.title}</span>
            <span className="acts">
              <Link className="btn ghost small" to={`/v/${source.videoId}?t=${source.at}`}>Open in VidWiz</Link>
              <button type="button" className="iconbtn" aria-label="Close" onClick={onClose}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13" /></svg>
              </button>
            </span>
          </div>
        </>
      )}
    </dialog>
  );
}

/** Guests can open any video and ask about it without an account. The link's start time carries over. */
function TryIt() {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const notify = useNotify();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const videoId = extractVideoId(value);
    if (!videoId) {
      setError('Enter a valid YouTube video link.');
      return;
    }
    setLoading(true);
    try {
      // Guests ask through a guest session; starting the chat also prepares the video.
      if (!sessionStorage.getItem('guestSessionId')) sessionStorage.setItem('guestSessionId', crypto.randomUUID());
      const conversation = await conversationsApi.createConversation({ scope: 'video', video_id: videoId });
      const start = extractStartSeconds(value);
      navigate(`/v/${videoId}?tab=ask&c=${conversation.id}${start ? `&t=${start}` : ''}`);
    } catch (cause) {
      notify.error(cause, 'Could not open the video', 'The video could not be opened.');
      setLoading(false);
    }
  };

  return (
    <>
    <form className="tryform" onSubmit={submit} noValidate>
      <label className="sr" htmlFor="try-link">YouTube video link</label>
      <input
        id="try-link"
        value={value}
        onChange={event => { setValue(event.target.value); setError(null); }}
        type="url"
        inputMode="url"
        autoComplete="off"
        autoCapitalize="off"
        spellCheck={false}
        placeholder="Paste a YouTube link"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? 'try-link-error' : 'try-link-hint'}
      />
      <button type="submit" className="btn primary" disabled={loading}>Ask about it</button>
    </form>
    {error
      ? <p id="try-link-error" role="alert" className="hint err">{error}</p>
      : <p id="try-link-hint" className="hint">No account needed to try it.</p>}
    </>
  );
}

export default function LandingPage() {
  const hydrated = useHydrated();
  const nav = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const heroCtas = useRef<HTMLDivElement>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [place, setPlace] = useState<Place>('computer');

  // The page is always dark, whatever the app theme, so overscroll matches too.
  useEffect(() => {
    document.documentElement.classList.add('landing-page');
    return () => document.documentElement.classList.remove('landing-page');
  }, []);

  // The nav turns solid once the page moves; the hero frame starts tilted back and settles flat.
  useEffect(() => {
    let ticking = false;
    const update = () => {
      ticking = false;
      const y = window.scrollY;
      const past = heroCtas.current ? heroCtas.current.getBoundingClientRect().bottom < 64 : false;
      nav.current?.classList.toggle('solid', y > 24);
      nav.current?.classList.toggle('past', past);
      if (!prefersReducedMotion()) stage.current?.style.setProperty('--tilt', Math.max(0, 1 - y / (window.innerHeight * 0.55)).toFixed(3));
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className={`landing${hydrated && prefersReducedMotion() ? ' manual' : ''}`}>
      <Seo
        title={LANDING_TITLE}
        description="Take timestamped notes on YouTube, find what was said later, and ask AI questions about a video or your library."
        path="/"
      />

      <Helmet defer={false}>
        <link rel="preload" as="image" href={mediaUrl('save-phone', 'webp')} media={MOBILE_MEDIA} fetchPriority="high" />
        <link rel="preload" as="image" href={mediaUrl('ext-hero', 'webp')} media={DESKTOP_MEDIA} fetchPriority="high" />
      </Helmet>

      <nav ref={nav} className="lnav" aria-label="Main">
        <div className="wrap">
          <Link className="logo" to="/"><img src="/brand/vidwiz-mark-color.svg" alt="" />VidWiz</Link>
          <Link className="login" to="/login">Log in</Link>
          <a className="btn primary small" href="#try">Try a video</a>
        </div>
      </nav>

      <main>
        <header className="hero" id="top">
          <div className="wrap">
            <h1>Keep the moments <span className="hl mark">worth coming back&nbsp;to.</span></h1>
            <p className="lede">Take timestamped notes on YouTube, find what was said later, and ask AI questions about a video or your library.</p>
            <div className="ctas">
              <div ref={heroCtas} className="ctas-row">
                <a className="btn primary desk-cta" href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">{CHROME_ICON}Add to Chrome</a>
                <a className="btn ghost desk-cta" href="#try">Try a video</a>
                <a className="btn primary phone-cta" href="#try">Try a video</a>
                <a className="btn ghost phone-cta" href="#find">See how it works</a>
              </div>
            </div>
          </div>
          <div className="stage-wrap">
            <div ref={stage} className="stage">
              <div className="only-desk">
                <Window><Clip priority media={DESKTOP_MEDIA} name="ext-hero" ratio="1920 / 1032" label="The VidWiz Chrome extension on YouTube. In fullscreen, Alt+S saves the moment at 14:19, then the extension lists it with its AI line and marks it on the video's timeline." cues={EXTENSION_CUES}>{KEYS}</Clip></Window>
              </div>
              <Phone className="only-phone"><Clip priority media={MOBILE_MEDIA} name="save-phone" ratio="540 / 1040" label="VidWiz on a phone. Tapping Save keeps the moment at 0:42 and its AI line is written." /></Phone>
            </div>
          </div>
        </header>

        <section className="feature" id="find" aria-labelledby="find-h">
          <div className="wrap">
            <Reveal className="copy">
              <Eyebrow n="01">Search</Eyebrow>
              <h2 id="find-h">Find that part <span className="hl mark">you remember.</span></h2>
              <p className="body">Search your moments and the transcripts of videos in your library. Open a result to return to that part of the video.</p>
            </Reveal>
            <Reveal delay={1} className="media">
              <div className="only-desk"><Browser url="vidwiz.online/search"><Clip media={DESKTOP_MEDIA} name="search-desktop" ratio="16 / 10" label="Searching for attention. Moments and transcript passages match, and a result opens the video at 13:04." /></Browser></div>
              <Phone className="only-phone"><Clip media={MOBILE_MEDIA} name="search-phone" ratio="540 / 1000" label="Searching for attention on a phone. A transcript result opens the video at 13:04." /></Phone>
            </Reveal>
          </div>
        </section>

        <section className="feature flip" id="ask" aria-labelledby="ask-h">
          <div className="wrap">
            <Reveal className="copy">
              <Eyebrow n="02">Ask</Eyebrow>
              <h2 id="ask-h">Ask your library. <span className="hl mark">Check the source.</span></h2>
              <p className="body">Ask questions across your saved videos. Every point links to the second it came from, so you can watch it for yourself.</p>
            </Reveal>
            <Reveal delay={1} className="media"><AskCard onOpen={setSource} /></Reveal>
          </div>
        </section>

        <section className="feature" id="anywhere" aria-labelledby="any-h">
          <div className="wrap">
            <Reveal className="copy">
              <Eyebrow n="03">Anywhere</Eyebrow>
              <h2 id="any-h">Save from <span className="hl mark">wherever you watch.</span></h2>
              <ul className="ways">
                {WAYS.map(way => (
                  <li key={way.key} className={way.key === place ? 'on' : undefined}>
                    <button type="button" className="pick" aria-pressed={way.key === place} aria-label={`Show saving ${way.title.toLowerCase()}`} onClick={() => setPlace(way.key)} />
                    <span className="ic">{way.icon}</span>
                    <span className="tab">{way.tab}</span>
                    <div>
                      <h3>{way.title}</h3>
                      <p>{way.body}</p>
                      {way.key === 'computer' && <a href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">Add to Chrome</a>}
                    </div>
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={1} className="media">
              <div className="places" data-place={place}>
                {place === 'computer' && (
                  <>
                    <div className="only-desk">
                      <Window><Clip media={DESKTOP_MEDIA} name="ext-shortcut" ratio="16 / 10" label="Watching fullscreen on YouTube, Alt+S saves the moment at 14:19 and the extension confirms it in the player." cues={SHORTCUT_CUES}>{KEYS}</Clip></Window>
                    </div>
                    <div className="only-phone">
                      <Window><Clip media={MOBILE_MEDIA} name="ext-phone" ratio="720 / 1280" label="Watching fullscreen on YouTube, Alt+S saves the moment at 14:19, then the extension lists it with its AI line and marks it on the video's timeline." cues={KEY_CUES}>{KEYS}</Clip></Window>
                    </div>
                  </>
                )}
                {place === 'phone' && <Phone><Clip name="save-phone" ratio="540 / 1040" label="VidWiz on a phone. Tapping Save keeps the moment at 0:42 and its AI line is written." /></Phone>}
                {place === 'web' && <Browser url="vidwiz.online"><Clip name="save-desktop" ratio="16 / 10" label="VidWiz playing a video. Alt+S saves the moment at 2:13 and its AI line is written." /></Browser>}
              </div>
              {WAYS.filter(way => way.key === place).map(way => (
                <p key={way.key} className="way-note only-phone">
                  {way.body}
                  {way.key === 'computer' && <> <a href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">Add to Chrome</a></>}
                </p>
              ))}
            </Reveal>
          </div>
        </section>

        <section className="pricing" id="pricing" aria-labelledby="price-h">
          <div className="wrap">
            <Reveal as="h2" id="price-h">Free to save <span className="hl mark">and search.</span></Reveal>
            <Reveal as="p" delay={1} className="body">Credits cover the extras. Every new account starts with {config.SIGNUP_CREDITS}.</Reveal>
            <div className="plans">
              <Reveal delay={1} className="plan free">
                <h3>Free</h3>
                <p className="price">$0</p>
                <ul>
                  <li>{CHECK}Save moments</li>
                  <li>{CHECK}Search moments and transcripts</li>
                  <li>{CHECK}Ask your library</li>
                </ul>
              </Reveal>
              <Reveal delay={2} className="plan">
                <h3>Credits</h3>
                <p className="price">{config.SIGNUP_CREDITS} <span>to start</span></p>
                <ul>
                  <li>AI line on a moment<b>1 credit</b></li>
                  <li>Ask about one video<b>5 credits</b></li>
                </ul>
                <p className="note">You pay for a video once. Questions after that are free, within a daily limit.</p>
              </Reveal>
            </div>
          </div>
        </section>

        <section className="try" id="try" aria-labelledby="try-h">
          <div className="wrap">
            <Reveal as="h2" id="try-h">Try it on a video <span className="hl mark">you're watching.</span></Reveal>
            <Reveal delay={1}><TryIt /></Reveal>
            <Reveal as="p" delay={2} className="alt"><Link to="/signup">Create a free account</Link> to save your own moments.</Reveal>
          </div>
        </section>
      </main>

      <footer className="lfoot">
        <div className="wrap">
          <div className="foot">
            <div className="brand">
              <a className="logo" href="#top" aria-label="VidWiz, back to top"><img src="/brand/vidwiz-mark-color.svg" alt="" />VidWiz</a>
              <p>Keep the moments worth coming back to.</p>
              <a className="btn ghost small" href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">{CHROME_ICON}Add to Chrome</a>
            </div>
            <nav className="cols" aria-label="Footer">
              <div><h3>Product</h3><a href="#find">Search</a><a href="#ask">Ask</a><a href="#anywhere">Save anywhere</a><a href="#pricing">Pricing</a></div>
              <div><h3>Get started</h3><a href="#try">Try a video</a><Link to="/signup">Create an account</Link><Link to="/login">Log in</Link></div>
              <div><h3>More</h3><a href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">Chrome extension</a><Link to="/support">Help</Link><Link to="/privacy">Privacy</Link><a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer">GitHub</a></div>
            </nav>
          </div>
          <div className="legal">
            <span>© {new Date().getFullYear()} VidWiz</span>
            <a href="#top">Back to top <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 10V2M2.5 5.5 6 2l3.5 3.5" /></svg></a>
          </div>
        </div>
      </footer>

      <SourceDialog source={source} onClose={() => setSource(null)} />
    </div>
  );
}
