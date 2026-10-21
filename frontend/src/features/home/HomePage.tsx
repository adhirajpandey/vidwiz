import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Chrome, Search, Smartphone, Sparkles } from 'lucide-react';
import config from '../../config';
import { useProfile } from '../../hooks/useProfile';
import PageTitle from '../../components/PageTitle';
import EmptyState from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/Input';
import AddVideoForm from '../library/AddVideoForm';
import VideoRow from '../library/VideoRow';
import { useLibrary } from '../library/queries';
import MomentFeed from './MomentFeed';

function MobileSearch() {
  const [value, setValue] = useState('');
  const navigate = useNavigate();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim().length >= 2) navigate(`/search?q=${encodeURIComponent(value.trim())}`);
  };
  return (
    <form role="search" onSubmit={submit} className="relative md:hidden">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input value={value} onChange={event => setValue(event.target.value)} placeholder="Search moments and transcripts" aria-label="Search" className="pl-9" />
    </form>
  );
}

function Welcome() {
  return (
    <EmptyState icon={<Sparkles className="size-5" />} title="Capture your first moment">
      <p>Save a moment while you watch, and VidWiz keeps what was said, an AI line, and your note. Then search or ask across everything.</p>
      <ul className="mt-4 space-y-2 text-left">
        <li className="flex gap-2"><Chrome className="mt-0.5 size-4 shrink-0" />Install the <a className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground" href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer">browser extension</a> and press Alt+S on YouTube.</li>
        <li className="flex gap-2"><Smartphone className="mt-0.5 size-4 shrink-0" />Capture from your phone with an <Link className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground" to="/settings#tokens">API token</Link>.</li>
      </ul>
    </EmptyState>
  );
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return 'Up late';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function HomePage() {
  const profile = useProfile();
  const recent = useLibrary({ per_page: 4, sort: 'activity_desc' });
  const firstName = profile.data?.name?.split(' ')[0];
  const isEmpty = recent.data?.total === 0;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageTitle title="Home" />
      <div className="space-y-4">
        <h1 className="display text-4xl">{firstName ? `${greeting()}, ${firstName}.` : `${greeting()}.`}</h1>
        <MobileSearch />
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <AddVideoForm />
          <Link to="/ask" className="inline-flex h-10 items-center justify-center gap-2 rounded-[9px] border border-border bg-card px-4 text-sm font-semibold hover:border-foreground/40">
            <Sparkles className="size-4" />Ask your library
          </Link>
        </div>
      </div>

      {isEmpty && <Welcome />}

      {recent.data && recent.data.videos.length > 0 && (
        <section aria-labelledby="continue">
          <div className="mb-3 flex items-baseline justify-between border-t-2 border-foreground pt-4">
            <h2 id="continue" className="display text-xl">Continue watching</h2>
            <Link to="/library" className="text-sm font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">All videos</Link>
          </div>
          <div className="grid gap-1 sm:grid-cols-2">
            {recent.data.videos.map(video => <VideoRow key={video.video_id} video={video} />)}
          </div>
        </section>
      )}

      <MomentFeed />
    </div>
  );
}
