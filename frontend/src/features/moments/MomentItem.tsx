import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Loader2, MoreHorizontal, Pencil, Sparkles, Trash2, X } from 'lucide-react';
import type { MomentRead } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import { TextArea } from '../../components/ui/Input';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import TimeChip from '../../components/ui/TimeChip';
import { cn } from '../../lib/utils';
import { normalizeApiError } from '../../api/errors';
import { clearActiveRow, setActiveRow, useActiveRow } from './rowFocus';
import MomentQuote from './MomentQuote';
import MomentStatus from './MomentStatus';
import ResolvePicker from './ResolvePicker';
import { playFrom, useDeleteMoment, useRequestAi, useUpdateMoment } from './queries';

interface Props {
  moment: MomentRead;
  /** Seek an on-page player; without it, the time links to the video page. */
  onSeek?: (seconds: number) => void;
  highlighted?: boolean;
  showQuote?: boolean;
}

export default function MomentItem({ moment, onSeek, highlighted, showQuote = true }: Props) {
  const [draft, setDraft] = useState(moment.note ?? '');
  const update = useUpdateMoment();
  const remove = useDeleteMoment();
  const requestAi = useRequestAi();
  const notify = useNotify();
  const at = moment.at_seconds;
  const activeRow = useActiveRow();
  const editing = activeRow?.id === moment.id && activeRow.mode === 'edit';
  const confirming = activeRow?.id === moment.id && activeRow.mode === 'delete';
  const stepBack = activeRow !== null && activeRow.id !== moment.id;
  const actionsButton = useRef<HTMLButtonElement>(null);
  const rowActionSelected = useRef(false);
  const deleteButton = useRef<HTMLButtonElement>(null);
  const noteInput = useRef<HTMLTextAreaElement>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  useEffect(() => () => { clearActiveRow(moment.id); }, [moment.id]);
  const cancelDelete = () => { if (remove.isPending) return; setDeleteError(null); clearActiveRow(moment.id); actionsButton.current?.focus(); };
  const stopEditing = () => { if (clearActiveRow(moment.id, 'edit')) actionsButton.current?.focus(); };
  const reallyDelete = () => remove.mutate(moment.id, {
    onSuccess: () => clearActiveRow(moment.id),
    onError: error => setDeleteError(normalizeApiError(error, 'The moment could not be deleted.').message),
  });
  const askDelete = () => { rowActionSelected.current = true; setDeleteError(null); setActiveRow({ id: moment.id, mode: 'delete' }); };

  const fail = (error: unknown, fallback: string) => {
    notify.error(error, 'Moment not updated', fallback);
  };

  // While the AI line is on its way, its status holds the AI line's place.
  const writing = moment.ai_status === 'queued' || moment.ai_status === 'waiting_transcript';
  const status = (
    <MomentStatus
      moment={moment}
      requesting={requestAi.isPending}
      onRequestAi={() => requestAi.mutate(moment.id, { onError: error => fail(error, 'The AI line could not be requested.') })}
    />
  );

  const saveNote = () => {
    if (update.isPending) return;
    update.mutate(
      { id: moment.id, body: { note: draft.trim() || null } },
      { onSuccess: stopEditing, onError: error => fail(error, 'The note could not be saved.') },
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
    <TimeChip seconds={at} onClick={() => onSeek(playFrom(moment))} />
  ) : (
    <Link to={`/v/${moment.video_id}?t=${playFrom(moment)}&m=${moment.id}`} aria-label={`Open at ${formatAt(at)}`}>
      <TimeChip seconds={at} />
    </Link>
  );

  return (
    <li
      id={`moment-${moment.id}`}
      // Only a highlighted row reaches past the column, so its tint has room around the text.
      className={cn('moment-anchor group py-3.5 transition-opacity', highlighted && '-mx-2 rounded-[10px] border-transparent bg-saved-soft px-2', stepBack && 'opacity-55')}
    >
      <div className="flex items-start gap-3">
        <div className="w-14 shrink-0 pt-0.5">{time}</div>
        <div className="min-w-0 flex-1 space-y-1.5">
          {writing && status}
          {moment.ai_text && (
            <p className="flex gap-2 text-[15px] leading-6" title={moment.ai_model ? `AI line by ${moment.ai_model}` : 'AI line'}>
              <Sparkles className="mt-1 size-3.5 shrink-0 text-muted-foreground" aria-label="AI line" />
              <span>{moment.ai_text}</span>
            </p>
          )}
          {editing ? (
            <div className="space-y-2">
              <TextArea
                ref={noteInput}
                value={draft}
                onChange={event => setDraft(event.target.value)}
                autoFocus
                aria-label="Your note"
                placeholder="Add your note"
                onKeyDown={event => {
                  if (event.nativeEvent.isComposing) return;
                  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (!event.repeat) saveNote(); }
                  if (event.key === 'Escape') { event.preventDefault(); stopEditing(); }
                }}
              />
              <div className="flex gap-2">
                <Button size="sm" variant="primary" onClick={saveNote} disabled={update.isPending}><Check className="size-3.5" />Save</Button>
                <Button size="sm" variant="ghost" onClick={() => { setDraft(moment.note ?? ''); stopEditing(); }}><X className="size-3.5" />Cancel</Button>
              </div>
            </div>
          ) : (
            moment.note && <p className="whitespace-pre-wrap border-l-2 border-foreground/25 pl-3 text-sm leading-6">{moment.note}</p>
          )}
          {showQuote && moment.quote && <MomentQuote quote={moment.quote} folded={Boolean(moment.ai_text || moment.note)} />}
          {!moment.ai_text && !moment.note && !moment.quote && !editing && (
            <p className="text-sm text-muted-foreground">Saved moment</p>
          )}
          {!writing && status}
          {confirming && (
            // Same as the extension: the question on its own line, Delete first, Escape cancels, no undo.
            <div
              role="group"
              aria-label="Confirm delete"
              onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelDelete(); } }}
              className="mt-1 flex flex-wrap items-center gap-1.5 rounded-[9px] bg-destructive/10 px-2.5 py-2 text-[13px] font-medium"
            >
              <span className="w-full">Delete this moment?</span>
              <Button ref={deleteButton} size="sm" autoFocus disabled={remove.isPending} onClick={reallyDelete} className="border-0 bg-destructive text-background hover:bg-destructive hover:brightness-105">Delete</Button>
              <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={cancelDelete}>Cancel</Button>
              {deleteError && <p role="alert" className="w-full text-xs text-destructive">{deleteError}</p>}
            </div>
          )}
        </div>
        <Menu>
          <MenuTrigger asChild>
            <Button ref={actionsButton} variant="ghost" size="icon" aria-label="Moment actions" className="opacity-60 group-hover:opacity-100">
              <MoreHorizontal className="size-4" />
            </Button>
          </MenuTrigger>
          <MenuContent onCloseAutoFocus={event => { if (rowActionSelected.current) { event.preventDefault(); (deleteButton.current ?? noteInput.current)?.focus(); } rowActionSelected.current = false; }}>
            <MenuItem onSelect={() => { rowActionSelected.current = true; setDraft(moment.note ?? ''); setActiveRow({ id: moment.id, mode: 'edit' }); }}>
              <Pencil className="size-4" />{moment.note ? 'Edit note' : 'Add note'}
            </MenuItem>
            <MenuItem className="text-destructive" onSelect={askDelete}>
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
