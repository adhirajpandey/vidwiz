import { ExternalLink } from 'lucide-react';
import { cn } from '../lib/utils';

interface WatchYouTubeButtonProps {
  videoId: string;
  className?: string;
  variant?: 'default' | 'red';
}

export function WatchYouTubeButton({ videoId, className = '', variant = 'default' }: WatchYouTubeButtonProps) {
  const variants = {
    default: "bg-secondary/50 text-foreground/70 hover:bg-secondary border-border hover:border-border/80",
    red: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 hover:bg-red-500/20 hover:border-red-500/30"
  };

  return (
    <a
      href={`https://www.youtube.com/watch?v=${videoId}`}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex-shrink-0 inline-flex items-center gap-2 px-3 py-2 text-xs font-medium border rounded-lg transition-all",
        variants[variant],
        className
      )}
    >
      <ExternalLink className="w-3.5 h-3.5" />
      <span>Watch on YouTube</span>
    </a>
  );
}

export default WatchYouTubeButton;
