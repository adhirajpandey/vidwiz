import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { History, Lock, Sparkles } from 'lucide-react';
import { conversationsApi } from '../../api';
import type { VideoRead } from '../../api';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import { useWizChat } from '../../hooks/useWizChat';
import WizChat from '../../components/wiz/WizChat';
import Button from '../../components/ui/Button';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import Spinner from '../../components/ui/Spinner';
import { formatRelative } from '../../lib/format';
import ChatLimitNotice from '../chat/ChatLimitNotice';
import { usePassageActions } from '../chat/usePassageActions';
import { useAskStatus, videoKeys } from './queries';

function Unlock({ cost, onUnlock }: { cost: number; onUnlock: () => void }) {
  const profile = useProfile();
  const balance = profile.data?.credits_balance;
  const short = balance !== undefined && balance < cost;
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-accent-soft text-accent"><Lock className="size-5" /></div>
      <h3 className="text-base font-semibold">Ask about this video</h3>
      <p className="mt-1.5 max-w-xs text-sm leading-6 text-muted-foreground">
        Unlocking costs {cost} credits once for this video. Every later question about it is free within your daily limit.
      </p>
      <Button variant="primary" className="mt-5" disabled={short} onClick={onUnlock}>
        <Sparkles className="size-4" />Unlock · {cost} credits
      </Button>
      <p className="mt-2 text-xs text-muted-foreground tabular">
        {balance === undefined ? '' : short ? `You have ${balance} credits. Get more in Settings.` : `You have ${balance} credits.`}
      </p>
    </div>
  );
}

function EarlierChats({ videoId, onPick }: { videoId: string; onPick: (id: number) => void }) {
  const chats = useQuery({
    queryKey: ['conversations', 'video', videoId],
    queryFn: () => conversationsApi.list({ scope: 'video', video_id: videoId, per_page: 10 }),
  });
  if (!chats.data?.conversations.length) return null;
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="ghost" size="sm"><History className="size-3.5" />Earlier chats</Button>
      </MenuTrigger>
      <MenuContent className="w-72">
        {chats.data.conversations.map(chat => (
          <MenuItem key={chat.id} onSelect={() => onPick(chat.id)} className="flex-col items-start gap-0.5">
            <span className="line-clamp-1">{chat.title}</span>
            <span className="text-xs text-muted-foreground">{formatRelative(chat.last_message_at)}</span>
          </MenuItem>
        ))}
      </MenuContent>
    </Menu>
  );
}

export default function AskPanel({ video, seek, signedIn, resumeId, onConversation }: {
  video: VideoRead;
  seek: (seconds: number) => void;
  signedIn: boolean;
  resumeId: number | null;
  onConversation: (id: number | null) => void;
}) {
  const status = useAskStatus(video.video_id);
  const queryClient = useQueryClient();
  const [unlocking, setUnlocking] = useState(false);
  const unlocked = Boolean(status.data?.unlocked) || unlocking || resumeId !== null;
  const chat = useWizChat(
    unlocked ? { scope: 'video', videoId: video.video_id } : null,
    video.transcript_available,
    {
      resumeId,
      onStarted: id => {
        onConversation(id);
        void queryClient.invalidateQueries({ queryKey: videoKeys.askStatus(video.video_id) });
        void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
      },
    },
  );
  const passages = usePassageActions({ videoId: video.video_id, seek, signedIn });

  if (status.isPending) return <div className="flex justify-center py-10"><Spinner /></div>;
  if (!unlocked && status.data) return <Unlock cost={status.data.cost} onUnlock={() => setUnlocking(true)} />;

  return (
    <WizChat
      chat={chat}
      isReady={video.transcript_available}
      suggestedQuestions={video.suggested_questions}
      passages={passages}
      className="h-[min(70dvh,640px)] lg:h-[calc(100dvh-13rem)]"
      header={
        <div className="flex items-center gap-1">
          {signedIn && <EarlierChats videoId={video.video_id} onPick={id => { onConversation(id); chat.resume(id); }} />}
        </div>
      }
      statusBanner={
        <>
          <ChatLimitNotice chat={chat} />
          {!video.transcript_available && (
            <div role="status" className="border-b border-border bg-accent-soft px-4 py-2.5 text-sm text-accent">Preparing the transcript…</div>
          )}
        </>
      }
    />
  );
}
