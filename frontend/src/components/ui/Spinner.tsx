import { cn } from '../../lib/utils';

export default function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label} className={cn('inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent text-muted-foreground', className)} />
  );
}
