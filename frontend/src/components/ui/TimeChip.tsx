import { formatClock } from '../../lib/format';
import { cn } from '../../lib/utils';

/** A playback position the user can jump to. */
export default function TimeChip({ seconds, onClick, className }: {
  seconds: number;
  onClick?: () => void;
  className?: string;
}) {
  const label = formatClock(seconds);
  const content = label;
  const classes = cn(
    'inline-flex shrink-0 items-center rounded-[5px] bg-saved px-1.5 py-px text-xs font-bold text-saved-foreground tabular',
    onClick && 'hover:brightness-105',
    className,
  );
  return onClick
    ? <button type="button" onClick={onClick} aria-label={`Play from ${label}`} className={classes}>{content}</button>
    : <span className={classes}>{content}</span>;
}
