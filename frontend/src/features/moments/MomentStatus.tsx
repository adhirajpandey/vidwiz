import { AlertCircle, Clock, Coins, Loader2, RotateCcw, Wand2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { MomentRead } from '../../api';
import Button from '../../components/ui/Button';

/** One line describing the moment's AI work, with the action that fixes it. */
export default function MomentStatus({ moment, onRequestAi, requesting }: {
  moment: MomentRead;
  onRequestAi?: () => void;
  requesting?: boolean;
}) {
  const line = 'flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground';
  switch (moment.ai_status) {
    case 'queued':
      return <p className={line}><Loader2 className="size-3.5 animate-spin" />Writing the AI line…</p>;
    case 'waiting_transcript':
      return <p className={line}><Clock className="size-3.5" />AI line waits for the transcript</p>;
    case 'no_transcript':
      return <p className={line}><AlertCircle className="size-3.5" />This video has no transcript, so there is no AI line or quote</p>;
    case 'insufficient_credits':
      return (
        <p className={line}>
          <Coins className="size-3.5 text-warning" />Not enough credits for the AI line.
          <Link to="/settings#credits" className="font-medium underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">Get credits</Link>
          {onRequestAi && <Button variant="ghost" size="sm" onClick={onRequestAi} disabled={requesting}>Try again</Button>}
        </p>
      );
    case 'failed':
      return (
        <p className={line}>
          <AlertCircle className="size-3.5 text-destructive" />The AI line failed.
          {onRequestAi && (
            <Button variant="ghost" size="sm" onClick={onRequestAi} disabled={requesting}>
              <RotateCcw className="size-3.5" />Retry, no extra charge
            </Button>
          )}
        </p>
      );
    case 'not_requested':
      return onRequestAi && moment.video_id && !moment.ai_text ? (
        <Button variant="ghost" size="sm" onClick={onRequestAi} disabled={requesting} className="-ml-2.5">
          <Wand2 className="size-3.5" />Add AI line, 1 credit
        </Button>
      ) : null;
    case 'ready':
      return null;
  }
}
