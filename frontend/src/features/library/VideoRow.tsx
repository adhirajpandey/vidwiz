import { Link, useSearchParams } from 'react-router-dom';
import type { ReactNode } from 'react';
import { Sparkles, StickyNote, Quote } from 'lucide-react';
import type { LibraryVideo } from '../../api';
import DurationThumbnail from '../../components/ui/DurationThumbnail';
import { formatRelative, videoTitle } from '../../lib/format';

const plural = (count: number, word: string) => `${count} ${count === 1 ? word : `${word}s`}`;

const KIND_ICON = { note: StickyNote, ai: Sparkles, quote: Quote };

// Marks the searched text in a title or channel.
function highlight(text: string, q: string | null): ReactNode {
  if (!q || q.length < 2) return text;
  const at = text.toLowerCase().indexOf(q.toLowerCase());
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark className="rounded-[3px] bg-saved/60 px-0.5 text-foreground">{text.slice(at, at + q.length)}</mark>{highlight(text.slice(at + q.length), q)}</>;
}

export default function VideoRow({ video, to }: { video: LibraryVideo; to?: string }) {
  const [params] = useSearchParams();
  // Match the Library controls: emphasize the sorted count and mark search matches.
  const q = params.get('q');
  const sort = params.get('sort');
  const chats = video.chat_count;
  const channel = video.metadata?.uploader;
  const latest = video.latest_moment;
  const LatestIcon = latest ? KIND_ICON[latest.kind] : null;
  return (
    <Link to={to ?? `/v/${video.video_id}`} className="flex items-start gap-4 rounded-[12px] p-2 hover:bg-muted">
      <DurationThumbnail video={video} className="w-32 sm:w-40" />
      <div className="min-w-0 flex-1 py-0.5">
        <p className="line-clamp-2 text-[15px] font-semibold leading-snug">{highlight(videoTitle(video.title, video.video_id), q)}</p>
        {channel && <p className="mt-0.5 truncate text-[13px] text-muted-foreground">{highlight(channel, q)}</p>}
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted-foreground tabular">
          {video.moment_count > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-[5px] bg-saved-soft px-1.5 py-px font-semibold text-foreground">{plural(video.moment_count, 'moment')}</span>
          ) : (
            <span>No moments</span>
          )}
          {chats > 0 && (
            <span className={sort === 'chats_desc' ? 'inline-flex items-center gap-1 rounded-[5px] bg-foreground/10 px-1.5 py-px font-semibold text-foreground' : 'inline-flex items-center gap-1'}>
              <Sparkles className="size-3" />{plural(chats, 'chat')}
            </span>
          )}
          <span>Active {formatRelative(video.last_activity_at)}</span>
          {video.transcript_status === 'pending' && <span>Transcript pending</span>}
          {video.transcript_status === 'unavailable' && <span>Transcript unavailable</span>}
        </p>
        {latest && LatestIcon && (
          <p className="mt-1.5 flex gap-1.5 text-[13px] leading-5 text-foreground/80">
            <LatestIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
            <span className="line-clamp-1">{latest.text}</span>
          </p>
        )}
      </div>
    </Link>
  );
}
