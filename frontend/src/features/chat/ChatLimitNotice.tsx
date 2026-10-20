import { Link } from 'react-router-dom';
import type { WizChatController } from '../../hooks/useWizChat';

function resetText(seconds: number | null): string {
  if (!seconds) return 'tomorrow';
  const hours = Math.ceil(seconds / 3600);
  return hours <= 1 ? 'within the hour' : `in about ${hours} hours`;
}

/** Shown in place of the composer banner when the daily message quota is used up. */
export default function ChatLimitNotice({ chat }: { chat: WizChatController }) {
  if (!chat.limit) return null;
  return (
    <div role="status" className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted px-4 py-2.5 text-sm">
      <span>
        You have used today&apos;s questions. More are available {resetText(chat.limit.resetSeconds)}.
        {chat.limit.kind === 'guest' && <> <Link to="/signup" className="font-medium underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">Sign up</Link> for more.</>}
      </span>
      <button type="button" onClick={chat.dismissLimit} className="text-xs text-muted-foreground hover:text-foreground">Dismiss</button>
    </div>
  );
}
