import { Play } from 'lucide-react';
import { formatClock } from '../../lib/format';
import { cn } from '../../lib/utils';

/** A playback position the user can jump to. */
export default function TimeChip({ seconds, onClick, className }: {
  seconds: number;
  onClick?: () => void;
  className?: string;
}) {
  const label = formatClock(seconds);
  const content = <><Play className="size-3 fill-current" aria-hidden="true" />{label}</>;
  const classes = cn(
    'inline-flex shrink-0 items-center gap-1 rounded-md bg-accent-soft px-1.5 py-0.5 font-mono text-xs font-medium text-accent tabular',
    onClick && 'hover:bg-accent/20',
    className,
  );
  return onClick
    ? <button type="button" onClick={onClick} aria-label={`Play from ${label}`} className={classes}>{content}</button>
    : <span className={classes}>{content}</span>;
}
