import { thumbnailUrl } from '../../lib/format';
import { cn } from '../../lib/utils';

export default function Thumbnail({ videoId, className }: { videoId: string; className?: string }) {
  return (
    <img
      src={thumbnailUrl(videoId)}
      alt=""
      loading="lazy"
      className={cn('aspect-video shrink-0 rounded-[8px] bg-muted object-cover', className)}
    />
  );
}
