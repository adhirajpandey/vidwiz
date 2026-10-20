import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronDown, Loader2, MoreHorizontal, Pencil, Sparkles, Trash2, X } from 'lucide-react';
import type { MomentRead } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import { TextArea } from '../../components/ui/Input';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import TimeChip from '../../components/ui/TimeChip';
import { cn } from '../../lib/utils';
import MomentStatus from './MomentStatus';
import ResolvePicker from './ResolvePicker';
import { startSeconds, useDeleteMoment, useRequestAi, useUpdateMoment } from './queries';

interface Props {
  moment: MomentRead;
  /** Seek an on-page player; without it, the time links to the video page. */
  onSeek?: (seconds: number) => void;
  highlighted?: boolean;
  showQuote?: boolean;
}

export default function MomentItem({ moment, onSeek, highlighted, showQuote = true }: Props) {
  const [editing, setEditing] = useState(false);
  // Without an AI line or note, the quote is the moment, so show it.
  const [quoteOpen, setQuoteOpen] = useState(!moment.ai_text && !moment.note);
  const [draft, setDraft] = useState(moment.note ?? '');
  const update = useUpdateMoment();
  const remove = useDeleteMoment();
  const requestAi = useRequestAi();
  const notify = useNotify();
  const start = startSeconds(moment);

  const fail = (error: unknown, fallback: string) => {
    notify.error(error, 'Moment not updated', fallback);
  };

  const saveNote = () => {
    update.mutate(
      { id: moment.id, body: { note: draft.trim() || null } },
      { onSuccess: () => setEditing(false), onError: error => fail(error, 'The note could not be saved.') },
    );
  };

  if (moment.resolve_status !== 'resolved') {
    return (
      <li className="rounded-lg border border-dashed border-border p-3">
        {moment.resolve_status === 'resolving' ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Finding the video for “{moment.pending_title}” at {formatAt(moment.at_seconds)}…
          </p>
        ) : (
          <ResolvePicker moment={moment} />
        )}
      </li>
    );
  }

  const time = onSeek ? (
    <TimeChip seconds={start} onClick={() => onSeek(start)} />
  ) : (
    <Link to={`/v/${moment.video_id}?t=${start}&m=${moment.id}`} aria-label={`Open at ${formatAt(start)}`}>
      <TimeChip seconds={start} />
    </Link>
  );

  return (
    <li
      id={`moment-${moment.id}`}
      className={cn('moment-anchor group -mx-2 rounded-[10px] px-2 py-3.5', highlighted && 'bg-saved-soft')}
    >
      <div className="flex items-start gap-3">
        <div className="w-14 shrink-0 pt-0.5">{time}</div>
        <div className="min-w-0 flex-1 space-y-1.5">
          {moment.ai_text && (
            <p className="flex gap-2 text-[15px] leading-6" title={moment.ai_model ? `AI line by ${moment.ai_model}` : 'AI line'}>
              <Sparkles className="mt-1 size-3.5 shrink-0 text-muted-foreground" aria-label="AI line" />
              <span>{moment.ai_text}</span>
            </p>
          )}
          {editing ? (
            <div className="space-y-2">
              <TextArea
                value={draft}
                onChange={event => setDraft(event.target.value)}
                autoFocus
                aria-label="Your note"
                placeholder="Add your note"
                onKeyDown={event => {
                  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) saveNote();
                  if (event.key === 'Escape') setEditing(false);
                }}
              />
              <div className="flex gap-2">
                <Button size="sm" variant="primary" onClick={saveNote} disabled={update.isPending}><Check className="size-3.5" />Save</Button>
                <Button size="sm" variant="ghost" onClick={() => { setDraft(moment.note ?? ''); setEditing(false); }}><X className="size-3.5" />Cancel</Button>
              </div>
            </div>
          ) : (
            moment.note && <p className="whitespace-pre-wrap border-l-2 border-foreground/25 pl-3 text-sm leading-6">{moment.note}</p>
          )}
          {showQuote && moment.quote && (quoteOpen ? (
            <blockquote className="border-l-2 border-border pl-3 text-sm leading-6 text-muted-foreground">
              {moment.quote}
            </blockquote>
          ) : (
            <button type="button" onClick={() => setQuoteOpen(true)} className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground">
              <ChevronDown className="size-3.5" />What was said
            </button>
          ))}
          {!moment.ai_text && !moment.note && !moment.quote && !editing && (
            <p className="text-sm text-muted-foreground">Saved moment</p>
          )}
          <MomentStatus
            moment={moment}
            requesting={requestAi.isPending}
            onRequestAi={() => requestAi.mutate(moment.id, { onError: error => fail(error, 'The AI line could not be requested.') })}
          />
        </div>
        <Menu>
          <MenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Moment actions" className="opacity-60 group-hover:opacity-100">
              <MoreHorizontal className="size-4" />
            </Button>
          </MenuTrigger>
          <MenuContent>
            <MenuItem onSelect={() => { setDraft(moment.note ?? ''); setEditing(true); }}>
              <Pencil className="size-4" />{moment.note ? 'Edit note' : 'Add note'}
            </MenuItem>
            <MenuItem
              className="text-destructive"
              onSelect={() => remove.mutate(moment.id, { onError: error => fail(error, 'The moment could not be deleted.') })}
            >
              <Trash2 className="size-4" />Delete
            </MenuItem>
          </MenuContent>
        </Menu>
      </div>
    </li>
  );
}

function formatAt(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
