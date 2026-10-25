import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Chrome, Search, Smartphone, Sparkles } from 'lucide-react';
import config from '../../config';
import { useProfile } from '../../hooks/useProfile';
import PageTitle from '../../components/PageTitle';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import AddVideoForm from '../library/AddVideoForm';
import DurationThumb from '../../components/ui/DurationThumbnail';
import type { LibraryVideo } from '../../api';
import { formatRelative, videoTitle } from '../../lib/format';
import { useLibrary } from '../library/queries';
import MomentFeed from './MomentFeed';
import Resurface from './Resurface';

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

const link = 'text-sm font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground';
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

function CompactHeader() {
  const profile = useProfile();
  const firstName = profile.data?.name?.split(' ')[0];
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="display text-[28px]">{firstName ? `${greeting()}, ${firstName}` : greeting()}</h1>
        <div className="sm:w-[24rem]"><AddVideoForm /></div>
      </div>
      <MobileSearch />
    </div>
  );
}

function SectionHead({ id, title, to, label }: { id: string; title: string; to: string; label: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2 id={id} className="display text-xl">{title}</h2>
      <Link to={to} className={link}>{label}</Link>
    </div>
  );
}

function VideoCard({ video }: { video: LibraryVideo }) {
  return (
    <Link to={`/v/${video.video_id}`} className="group block w-40 shrink-0 snap-start rounded-[12px] sm:w-auto">
      <DurationThumb video={video} className="w-full" />
      <p className="mt-2 line-clamp-2 text-sm font-semibold leading-snug group-hover:underline group-hover:decoration-foreground/30 group-hover:underline-offset-4">{videoTitle(video.title, video.video_id)}</p>
      <p className="mt-0.5 truncate text-xs text-muted-foreground tabular">{plural(video.moment_count, 'moment')} · {formatRelative(video.last_activity_at)}</p>
    </Link>
  );
}

function RecentStrip({ videos }: { videos: LibraryVideo[] }) {
  return (
    <section aria-labelledby="recent-videos">
      <SectionHead id="recent-videos" title="Recent videos" to="/library" label="All videos" />
      <div className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:scroll-px-0 sm:grid-cols-4 sm:overflow-visible sm:px-0">
        {videos.slice(0, 4).map(video => <VideoCard key={video.video_id} video={video} />)}
      </div>
    </section>
  );
}

export default function HomePage() {
  const recent = useLibrary({ per_page: 4, sort: 'activity_desc' });
  const videos = recent.data?.videos ?? [];
  return (
    <div className="mx-auto max-w-3xl space-y-7">
      <PageTitle title="Home" />
      <CompactHeader />
      {recent.data?.total === 0 && <Welcome />}
      {videos.length > 0 && <RecentStrip videos={videos} />}
      {recent.isError && !recent.data && <ErrorState compact headingLevel={3} title="Recent videos did not load" message="Check your connection and try again." onRetry={() => void recent.refetch()} />}
      <Resurface />
      <MomentFeed />
    </div>
  );
}
