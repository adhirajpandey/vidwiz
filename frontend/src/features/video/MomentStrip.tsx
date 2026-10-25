import { useLayoutEffect, useRef, useState } from 'react';
import type { MomentRead } from '../../api';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import { Tooltip } from '../../components/ui/Tooltip';
import { formatClock } from '../../lib/format';
import { playFrom } from '../moments/queries';
import { groupMarks } from './groupMarks';
import { useVideoMoments } from './queries';

const preview = (moment: MomentRead) => moment.ai_text ?? moment.note ?? moment.quote;
const pin = 'absolute -top-1 grid h-6 -translate-x-1/2 place-items-center rounded-sm';
const ring = 'shadow-[0_0_0_1.5px_hsl(var(--background))]';

/**
 * Where your moments sit in the video: caption-yellow marks on a thin rail.
 * Marks too close to tell apart merge into a numbered marker that lists them.
 */
export default function MomentStrip({ videoId, duration, playhead, onSeek }: {
  videoId: string;
  duration: number;
  playhead: number | null;
  onSeek: (seconds: number) => void;
}) {
  const moments = useVideoMoments(videoId, true);
  const rail = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = rail.current;
    if (!node) return;
    setWidth(node.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const at = (seconds: number) => `${Math.min(100, (seconds / duration) * 100)}%`;
  const groups = groupMarks((moments.data ?? []).filter(moment => moment.resolve_status === 'resolved'), duration, width);

  return (
    <div ref={rail} role="group" aria-label="Your moments in this video" className="relative h-4">
      <div className="absolute inset-x-0 top-1.5 h-1 rounded-full bg-border" />
      {playhead !== null && <div className="absolute left-0 top-1.5 h-1 rounded-full bg-muted-foreground/60" style={{ width: at(playhead) }} />}
      {groups.map(group => {
        const first = group[0];
        if (group.length === 1) {
          const text = preview(first);
          return (
            <Tooltip key={first.id} label={<><span className="block tabular">{formatClock(first.at_seconds)}</span>{text && <span className="line-clamp-2">{text}</span>}</>}>
              <button type="button" onClick={() => onSeek(playFrom(first))} aria-label={`Play moment at ${formatClock(first.at_seconds)}`}
                className={`group/mark ${pin} w-3.5`} style={{ left: at(first.at_seconds) }}>
                <span className={`h-4 w-1 rounded-full bg-saved transition-transform group-hover/mark:scale-y-125 ${ring}`} />
              </button>
            </Tooltip>
          );
        }
        const label = `${group.length} moments, ${formatClock(first.at_seconds)} to ${formatClock(group[group.length - 1].at_seconds)}`;
        return (
          <Menu key={first.id}>
            <Tooltip label={label}>
              <MenuTrigger asChild>
                <button type="button" aria-label={label} className={`group/mark ${pin} w-[22px]`} style={{ left: at(first.at_seconds) }}>
                  <span className={`grid h-4 min-w-4 place-items-center rounded-full bg-saved px-1 text-[10px] font-bold leading-none text-saved-foreground tabular transition-transform group-hover/mark:scale-110 group-data-[state=open]/mark:scale-110 ${ring}`}>{group.length}</span>
                </button>
              </MenuTrigger>
            </Tooltip>
            <MenuContent align="start" className="max-h-80 w-80 max-w-[calc(100vw-2rem)] overflow-y-auto">
              {group.map(moment => (
                <MenuItem key={moment.id} onSelect={() => onSeek(playFrom(moment))} className="items-start gap-3">
                  <span className="w-12 shrink-0 pt-px text-xs font-semibold text-muted-foreground tabular">{formatClock(moment.at_seconds)}</span>
                  <span className="line-clamp-2">{preview(moment) ?? 'Saved moment'}</span>
                </MenuItem>
              ))}
            </MenuContent>
          </Menu>
        );
      })}
    </div>
  );
}
