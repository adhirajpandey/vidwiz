import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Moon, Search, Sun } from 'lucide-react';
import { conversationsApi } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import { useTheme } from '../../hooks/useTheme';
import { formatClock } from '../../lib/format';
import { LANDING_TITLE } from '../../lib/title';
import { extractVideoId } from '../../lib/videoUtils';
import Seo from '../../components/Seo';
import './landing.css';

// Example content comes from a real library: Josh Kaufman's TEDxCSU talk and
// the AI lines VidWiz wrote for moments saved on it.
const EXAMPLE = {
  videoId: '5MgBikgcWnY',
  title: 'The first 20 hours: how to learn anything, Josh Kaufman',
  duration: 1167,
  pausedAt: 587,
};
const SAVED = [
  { at: 300, ai: 'The famous 10000 hour rule comes from experts at the top of their fields practicing extensively' },
  { at: 120, ai: 'He was troubled by the common belief that after having a child you will never have free time again' },
];
const NEW_MOMENT = { at: EXAMPLE.pausedAt, ai: 'The first step is to deconstruct the skill and decide exactly what you want to be able to do' };

const pct = (seconds: number) => `${(seconds / EXAMPLE.duration) * 100}%`;

function Time({ seconds }: { seconds: number }) {
  return <span className="time">{formatClock(seconds)}</span>;
}

function ExampleVideo() {
  const [saved, setSaved] = useState(false);
  const moments = saved ? [NEW_MOMENT, ...SAVED].slice(0, 2) : SAVED;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 's' && !(event.target as HTMLElement).closest('input, textarea')) setSaved(true);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="demo" aria-label="Example: a video with its saved moments">
      <div className="screen" style={{ backgroundImage: `url(https://i.ytimg.com/vi/${EXAMPLE.videoId}/maxresdefault.jpg)` }}>
        <span className="play" aria-hidden="true" />
        <div className="bar">
          <span>{formatClock(EXAMPLE.pausedAt)}</span>
          <div className="scrub">
            <span className="done" style={{ width: pct(EXAMPLE.pausedAt) }} />
            {[...SAVED, ...(saved ? [NEW_MOMENT] : [])].map(moment => <span key={moment.at} className="tick" style={{ left: pct(moment.at) }} />)}
          </div>
          <span>{formatClock(EXAMPLE.duration)}</span>
        </div>
      </div>
      <div className="controls">
        <button type="button" className="btn yellow save" onClick={() => setSaved(true)}>Save this moment <kbd>S</kbd></button>
        <span className="hint">{saved ? `Saved at ${formatClock(EXAMPLE.pausedAt)}.` : EXAMPLE.title}</span>
      </div>
      <div className="tray">
        <div className="tray-head"><span>Your moments</span><span>{saved ? 3 : 2} saved</span></div>
        {moments.map(moment => (
          <div key={moment.at} className={moment === NEW_MOMENT ? 'moment new' : 'moment'}>
            <Time seconds={moment.at} />
            <p>{moment.ai}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Result({ source, at, children }: { source: string; at: number; children: ReactNode }) {
  return (
    <div className="result">
      <span className="src">{source}</span>
      <Time seconds={at} />
      <p>{children}</p>
    </div>
  );
}

function Cite({ at, title }: { at: number; title: string }) {
  return <span className="cite"><Time seconds={at} />{title}</span>;
}

/** Guests can open any video and ask about it without an account. */
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
      setError('Paste a YouTube video link.');
      return;
    }
    setLoading(true);
    try {
      // Guests ask through a guest session; starting the chat also prepares the video.
      if (!sessionStorage.getItem('guestSessionId')) sessionStorage.setItem('guestSessionId', crypto.randomUUID());
      const conversation = await conversationsApi.createConversation({ scope: 'video', video_id: videoId });
      navigate(`/v/${videoId}?tab=ask&c=${conversation.id}`);
    } catch (cause) {
      notify.error(cause, 'Could not open the video', 'The video could not be opened.');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <div className="try">
        <input
          value={value}
          onChange={event => { setValue(event.target.value); setError(null); }}
          placeholder="Paste a YouTube link"
          aria-label="YouTube link"
        />
        <button type="submit" className="btn yellow" disabled={loading || !value.trim()}>Ask about it</button>
      </div>
      {error ? <p role="alert" className="try-note">{error}</p> : <p className="try-note">No account needed to try it.</p>}
    </form>
  );
}

export default function LandingPage() {
  const { theme, toggle } = useTheme();
  return (
    <div className="landing">
      <Seo
        title={LANDING_TITLE}
        description="Save the exact words from any YouTube moment you tap. Search what was said weeks later, and ask questions across everything you have watched."
        path="/"
      />
      <header className="hero">
        <div className="wrap">
          <nav className="nav" aria-label="Main">
            <Link className="logo" to="/"><img src="/brand/vidwiz-mark-color.svg" alt="" />VidWiz</Link>
            <div className="links">
              <a href="#search">How it works</a>
              <a href="#pricing">Pricing</a>
              <button type="button" className="theme" aria-label="Toggle theme" onClick={toggle}>
                {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </button>
              <Link className="keep" to="/login">Log in</Link>
            </div>
            <Link className="btn yellow small" to="/signup">Start free</Link>
          </nav>

          <div className="hero-grid">
            <div>
              <h1>
                <span className="line"><span className="cap">You just heard something worth keeping.</span></span>
                <span className="line"><span className="cap">Tap once. Find it later.</span></span>
              </h1>
              <p className="lede">
                VidWiz saves the exact words from any moment you tap on YouTube. Weeks later, search what was said, replay the second it was said, or ask questions across everything you have watched.
              </p>
              <div className="ctas">
                <Link className="btn yellow" to="/signup">Start free</Link>
                <a className="btn line" href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">Add to Chrome</a>
              </div>
              <p className="fine">{config.SIGNUP_CREDITS} free credits. Saving and searching never cost anything.</p>
            </div>
            <ExampleVideo />
          </div>
        </div>
      </header>

      <main>
        <section className="band" id="search">
          <div className="wrap split">
            <div className="copy">
              <h2>Weeks later, search what was said.</h2>
              <p>You remember the idea, not the video. Search your moments and every transcript in your library, and open the video at the second it was said.</p>
            </div>
            <div className="search" aria-label="Example search">
              <div className="query"><Search aria-hidden="true" />learning</div>
              <Result source="Your moment in The secrets of learning a new language" at={300}>
                Language <mark>learning</mark> sticks when it becomes a pleasant daily activity tailored to your preferences like apps or podcasts
              </Result>
              <Result source="Your moment in Learning how to learn" at={300}>
                <mark>Learning</mark> uses two modes and is explained with a pinball machine analogy
              </Result>
              <Result source="Transcript of The first 20 hours" at={670}>
                So the <mark>learning</mark> becomes a way of getting better at noticing when you're making a mistake.
              </Result>
              <Result source="Transcript of The secrets of learning a new language" at={463}>
                If you <mark>learn</mark> in small chunks every day in a way that you enjoy.
              </Result>
            </div>
          </div>
        </section>

        <section className="band ask">
          <div className="wrap split">
            <div className="copy">
              <h2>Ask across everything you have watched.</h2>
              <p>Answers come only from your own videos, with the moment each point came from. Play it, or save it as a new moment.</p>
            </div>
            <div>
              <p className="question">What practical advice do my saved videos give about learning a new skill?</p>
              <div className="answer">
                <p>
                  Break the skill into smaller pieces and practise the most important parts first <Cite at={562} title="The first 20 hours" />. Learn just enough to notice your own mistakes, and don't let collecting books become a way to put off <span className="nowrap">practice <Cite at={657} title="The first 20 hours" />.</span>
                </p>
                <p>
                  Turn learning into something pleasant you can do every day, like apps, podcasts or a show you love <Cite at={269} title="The secrets of learning a new language" />. When you review, recall what you learned instead of rereading <span className="nowrap">it <Cite at={992} title="Learning how to learn" />.</span>
                </p>
              </div>
              <p className="note">Answered from three videos in this library. Questions across your library are free.</p>
            </div>
          </div>
        </section>

        <section className="band">
          <div className="wrap">
            <h2>Save from wherever you watch.</h2>
            <div className="where">
              <div><span className="big"><kbd>Alt</kbd> <kbd>S</kbd></span><h3>On your computer</h3><p>The Chrome extension saves the moment on any YouTube tab without leaving the video.</p></div>
              <div><span className="big">One tap</span><h3>On your phone</h3><p>Tap a floating button while YouTube plays, or share the video to VidWiz.</p></div>
              <div><span className="big">Paste a link</span><h3>On the web</h3><p>Open any video in VidWiz and save from the player, the transcript, or an answer.</p></div>
            </div>
          </div>
        </section>

        <section className="band" id="pricing" style={{ paddingTop: 0 }}>
          <div className="wrap split">
            <div className="copy">
              <h2>Free to save and search.</h2>
              <p>Credits are only for AI. You start with {config.SIGNUP_CREDITS}.</p>
              <div className="ctas"><Link className="btn ink" to="/signup">Create a free account</Link></div>
            </div>
            <div className="rows">
              <div className="prow"><span>Saving moments, search, questions across your library</span><b>Free</b></div>
              <div className="prow"><span>AI line on a moment</span><b>1 credit</b></div>
              <div className="prow"><span>Asking about one video, once per video</span><b>5 credits</b></div>
              <div className="prow total"><span>New accounts start with</span><b>{config.SIGNUP_CREDITS} credits</b></div>
            </div>
          </div>
        </section>

        <section className="closing">
          <div className="wrap">
            <h2>Try it on a video you are watching.</h2>
            <TryIt />
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap">
          <span>VidWiz</span>
          <Link to="/privacy">Privacy</Link>
          <a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
