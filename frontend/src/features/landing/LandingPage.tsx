import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, BookmarkPlus, Chrome, Search, Smartphone, Sparkles } from 'lucide-react';
import { conversationsApi } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import { extractVideoId } from '../../lib/videoUtils';
import Seo from '../../components/Seo';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

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
    <form onSubmit={submit} className="mx-auto w-full max-w-xl space-y-2">
      <div className="flex gap-2">
        <Input
          value={value}
          onChange={event => { setValue(event.target.value); setError(null); }}
          placeholder="Paste a YouTube link to try it"
          aria-label="YouTube link"
          className="h-11"
        />
        <Button type="submit" variant="primary" className="h-11" disabled={loading || !value.trim()}>
          Ask <ArrowRight className="size-4" />
        </Button>
      </div>
      {error ? <p role="alert" className="text-xs text-destructive">{error}</p> : <p className="text-xs text-muted-foreground">No account needed to try it.</p>}
    </form>
  );
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent">{icon}</div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1.5 text-sm leading-6 text-muted-foreground">{children}</p>
    </div>
  );
}

export default function LandingPage() {
  return (
    <>
      <Seo
        title="VidWiz — remember what you watch"
        description="Capture moments while you watch YouTube, find them again by searching what was said, and ask questions across everything you have watched."
        path="/"
      />
      <div className="space-y-20 py-8 md:py-16">
        <section className="space-y-6 text-center">
          <h1 className="mx-auto max-w-2xl text-4xl font-semibold tracking-tight md:text-5xl">
            Tap while watching. VidWiz remembers what was said.
          </h1>
          <p className="mx-auto max-w-xl text-base leading-7 text-muted-foreground">
            Save the moments that matter on YouTube, find them again weeks later by searching what was said, and ask questions across everything you have watched.
          </p>
          <TryIt />
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <Feature icon={<BookmarkPlus className="size-5" />} title="Capture in one tap">
            Each moment keeps the exact words from the video, an optional AI line, and your note. Taps close together merge, so nothing is duplicated.
          </Feature>
          <Feature icon={<Search className="size-5" />} title="Find it again">
            Search your moments and every transcript in your library. Results open the video at the second it was said.
          </Feature>
          <Feature icon={<Sparkles className="size-5" />} title="Ask across your library">
            Ask a question and get an answer built from your own videos, with citations you can play and save.
          </Feature>
        </section>

        <section className="grid items-center gap-8 md:grid-cols-2">
          <div className="space-y-3">
            <h2 className="text-2xl font-semibold tracking-tight">Capture wherever you watch</h2>
            <ul className="space-y-3 text-sm leading-6 text-muted-foreground">
              <li className="flex gap-3"><Chrome className="mt-1 size-4 shrink-0 text-foreground" />On desktop, press Alt+S with the <a href={config.CHROME_WEBSTORE_URL} className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">browser extension</a>.</li>
              <li className="flex gap-3"><Smartphone className="mt-1 size-4 shrink-0 text-foreground" />On your phone, tap a floating button from an automation, or share a video to VidWiz.</li>
              <li className="flex gap-3"><BookmarkPlus className="mt-1 size-4 shrink-0 text-foreground" />On the web, capture from the player, the transcript, or any answer.</li>
            </ul>
          </div>
          <div className="rounded-xl border border-border bg-card p-5 text-sm">
            <h3 className="mb-3 font-semibold">Simple credits</h3>
            <ul className="space-y-2 text-muted-foreground">
              <li className="flex justify-between gap-4"><span>Moments, search, library questions</span><span className="font-medium text-foreground">Free</span></li>
              <li className="flex justify-between gap-4"><span>AI line on a moment</span><span className="font-medium text-foreground tabular">1 credit</span></li>
              <li className="flex justify-between gap-4"><span>Ask about a video, once per video</span><span className="font-medium text-foreground tabular">5 credits</span></li>
              <li className="flex justify-between gap-4 border-t border-border pt-2"><span>New accounts start with</span><span className="font-medium text-foreground tabular">{config.SIGNUP_CREDITS} credits</span></li>
            </ul>
            <Link to="/signup" className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-lg bg-accent text-sm font-medium text-accent-foreground hover:opacity-90">Create a free account</Link>
          </div>
        </section>

        <footer className="flex flex-wrap justify-center gap-4 border-t border-border pt-6 text-xs text-muted-foreground">
          <Link to="/privacy" className="hover:text-foreground">Privacy</Link>
          <a href="https://github.com/adhirajpandey/vidwiz" target="_blank" rel="noopener noreferrer" className="hover:text-foreground">GitHub</a>
        </footer>
      </div>
    </>
  );
}
