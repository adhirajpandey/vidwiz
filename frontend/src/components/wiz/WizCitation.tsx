import { createContext, useContext, useState } from 'react';
import type { DataMessagePartProps } from '@assistant-ui/react';
import { Link } from 'react-router-dom';
import { Bookmark, BookmarkCheck } from 'lucide-react';
import type { CitationPart, Passage } from '../../api/messageParts';
import { formatClock } from '../../lib/format';
import { Tooltip } from '../ui/Tooltip';

export interface PassageActions {
  /** Play the passage: seek the on-page player, or open its video. */
  watch: (passage: Passage) => void;
  watchHref?: (passage: Passage) => string | undefined;
  /** Keep the passage as a moment; absent for guests. */
  save?: (passage: Passage) => Promise<void>;
  /** Library answers name the video each passage comes from. */
  videoLabel?: (videoId: string) => string | undefined;
}

const PassageContext = createContext<PassageActions>({ watch: () => undefined });
export const WizPassageProvider = PassageContext.Provider;

function SavePassage({ passage, save }: { passage: Passage; save: (passage: Passage) => Promise<void> }) {
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const saved = state === 'saved';
  return (
    <Tooltip label={saved ? 'Saved as a moment' : 'Save as a moment, free'}>
    <button
      type="button"
      className="wiz-save"
      disabled={state !== 'idle'}
      aria-label={saved ? 'Saved as a moment' : 'Save passage as a moment'}
      onClick={async () => {
        setState('saving');
        try {
          await save(passage);
          setState('saved');
        } catch {
          setState('idle');
        }
      }}
    >
      {saved ? <BookmarkCheck className="size-3.5" /> : <Bookmark className="size-3.5" />}
    </button>
    </Tooltip>
  );
}

export function WatchPassage({ passage }: { passage: Passage }) {
  const { watch, watchHref, save, videoLabel } = useContext(PassageContext);
  const start = formatClock(passage.start_seconds);
  const end = formatClock(passage.end_seconds);
  const video = passage.video_id ? videoLabel?.(passage.video_id) : undefined;
  const href = watchHref?.(passage);
  const label = `Watch ${video ? `${video} ` : ''}from ${start} to ${end}`;
  const content = <><span className="wiz-time">{start}</span>{video ? <span className="wiz-video">{video}</span> : 'Watch'}</>;
  return (
    <span className="wiz-passage">
      <Tooltip label={<>{video && <span className="block">{video}</span>}{start} to {end}, starting 2 seconds early</>}>
        {href ? <Link to={href} className="wiz-watch" aria-label={label}>{content}</Link> : (
          <button type="button" className="wiz-watch" aria-label={label} onClick={() => watch(passage)}>{content}</button>
        )}
      </Tooltip>
      {save && <SavePassage passage={passage} save={save} />}
    </span>
  );
}

/** Standalone citations from messages saved before block answers. */
export default function WizCitation({ data }: DataMessagePartProps<CitationPart>) {
  const { watch } = useContext(PassageContext);
  const label = formatClock(data.start_seconds);
  return (
    <button
      type="button"
      aria-label={`Seek video to ${label}`}
      onClick={() => watch({ chunk_ids: [data.chunk_id], start_seconds: data.start_seconds, end_seconds: data.end_seconds })}
      className="mx-0.5 my-1 inline-flex items-center rounded-[5px] bg-saved px-1.5 text-xs font-bold text-saved-foreground tabular hover:brightness-105"
    >
      {label}
    </button>
  );
}
