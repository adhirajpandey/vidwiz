import { cn } from '../../lib/utils';

interface ErrorStateProps {
  title: string;
  message: string;
  referenceId?: string;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

export default function ErrorState({
  title,
  message,
  referenceId,
  onRetry,
  retryLabel = 'Try again',
  compact = false,
  headingLevel = 2,
  className,
}: ErrorStateProps) {
  const Heading =
    headingLevel === 2 ? 'h2' : headingLevel === 3 ? 'h3' : 'h4';

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'px-4 py-8' : 'px-6 py-14',
        className
      )}
    >
      <Heading className="text-base font-semibold text-red-600 dark:text-red-400">
        {title}
      </Heading>
      <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
        {message}
      </p>
      {referenceId && (
        <p className="mt-2 max-w-md break-all font-mono text-xs text-muted-foreground/70">
          Reference: {referenceId}
        </p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-secondary/80 focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
