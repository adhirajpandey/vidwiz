import { History } from 'lucide-react';
import type { ConversationSummary } from '../../api';
import Button from '../../components/ui/Button';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import { formatRelative } from '../../lib/format';
import { cn } from '../../lib/utils';

/** Chat history as a menu in the chat header; the open chat is marked. Hidden until there are chats. */
export default function ChatHistoryMenu({ chats, activeId, onPick, className }: {
  chats: ConversationSummary[] | undefined;
  activeId: number | null;
  onPick: (id: number) => void;
  className?: string;
}) {
  if (!chats?.length) return null;
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="ghost" size="sm" className={cn('whitespace-nowrap', className)}><History className="size-3.5" />Chat history</Button>
      </MenuTrigger>
      <MenuContent className="w-72 max-h-80 overflow-y-auto" align="start">
        {chats.map(chat => (
          <MenuItem key={chat.id} onSelect={() => onPick(chat.id)} aria-current={chat.id === activeId || undefined} className={cn('flex-col items-start gap-0.5', chat.id === activeId && 'bg-muted')}>
            <span className="line-clamp-1">{chat.title}</span>
            <span className="text-xs text-muted-foreground">{formatRelative(chat.last_message_at)}</span>
          </MenuItem>
        ))}
      </MenuContent>
    </Menu>
  );
}
