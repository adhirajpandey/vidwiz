import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Check, ChevronDown, Coins, Settings, SquarePen } from 'lucide-react';
import { momentsApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../../components/ui/Menu';
import { formatClock } from '../../lib/format';
import { cn } from '../../lib/utils';
import { momentKeys } from '../moments/queries';

const kbd = 'rounded-[5px] border-[1.5px] px-1.5 text-xs font-semibold';

/**
 * Capture the current playback position with an optional note. Save follows the
 * AI line default from Settings; the arrow offers both ways, default checked.
 * S saves from anywhere on the page, Shift S the other way.
 */
/** One way to save. The default is checked and has the plain S key; the other uses Shift S. */
function SaveOption({ label, cost, isDefault, onSelect }: {
  label: string;
  cost: string;
  isDefault: boolean;
  onSelect: () => void;
}) {
  return (
    <MenuItem onSelect={onSelect}>
      <Check className={cn('size-4 shrink-0', !isDefault && 'invisible')} aria-hidden="true" />
      <span className="flex-1 font-medium">{label}{isDefault && <span className="sr-only">, default</span>}</span>
      <span className="text-xs text-muted-foreground">{cost}</span>
      <span className="hidden w-14 justify-end sm:flex">
        <kbd className={`${kbd} border-border text-muted-foreground`}>{isDefault ? 'S' : 'Shift S'}</kbd>
      </span>
    </MenuItem>
  );
}

export default function CaptureBar({ videoId, currentTime, playhead, onView }: {
  videoId: string;
  currentTime: () => number | null;
  playhead: number | null;
  onView?: (momentId: number) => void;
}) {
  const [noteOpen, setNoteOpen] = useState(false);
  const noteButton = useRef<HTMLButtonElement>(null);
  const savingRef = useRef(false);
  const profile = useProfile();
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [menuWidth, setMenuWidth] = useState<number>();
  const group = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const notify = useNotify();
  // Saving waits for the profile, so a save never guesses the AI line default.
  const ready = profile.data !== undefined && !saving;
  const aiDefault = profile.data?.ai_moments_default ?? false;
  const balance = profile.data?.credits_balance;
  const broke = balance === 0;
  const aiCost = broke ? 'No credits' : '1 credit';

  const capture = async (ai: boolean) => {
    if (!ready || savingRef.current) return;
    savingRef.current = true;
    const at = Math.floor(currentTime() ?? 0);
    setSaving(true);
    try {
      const result = await momentsApi.capture({
        video: videoId, at, note: note.trim() || null, ai, source: 'web',
      });
      setNote('');
      setNoteOpen(false);
      void queryClient.invalidateQueries({ queryKey: momentKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['library'] });
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
      const title = result.merged ? 'Added to a nearby moment' : `Moment saved at ${formatClock(at)}`;
      notify.success(title, '', { label: 'View moment', onClick: () => onView?.(result.moment.id) });
    } catch (cause) {
      notify.error(cause, 'Moment not saved', 'The moment could not be saved.');
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };
  const captureRef = useRef(capture);
  captureRef.current = capture;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 's' || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, [contenteditable="true"], [role="dialog"], [role="menu"]')) return;
      event.preventDefault();
      if (event.repeat) return;
      void captureRef.current(event.shiftKey ? !aiDefault : aiDefault);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [aiDefault]);

  return (
    <div className="space-y-2">
    {broke && aiDefault && (
      <p role="status" className="flex flex-wrap items-center gap-1.5 rounded-[10px] border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
        <Coins className="size-4 text-warning" />No credits left, so saves won't get an AI line.
        <Link to="/settings#credits" className="font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">Get credits</Link>
      </p>
    )}
    {noteOpen && (
      <div className="space-y-1">
        <Input value={note} onChange={event => setNote(event.target.value)} placeholder="Note (optional)" aria-label="Note for this moment" autoFocus className="h-11"
          onKeyDown={event => { if (event.key === 'Escape') { setNote(''); setNoteOpen(false); noteButton.current?.focus(); } }} />
        <div className="flex justify-end">
          <button type="button" onClick={() => { setNote(''); setNoteOpen(false); noteButton.current?.focus(); }} className="text-xs font-medium text-muted-foreground hover:text-foreground">Cancel note</button>
        </div>
      </div>
    )}
    <form
      // V1 phones: one row, so the pinned block stays short.
      className="flex flex-row items-center gap-2"
      onSubmit={event => { event.preventDefault(); void capture(aiDefault); }}
    >
      <div ref={group} className="flex min-w-0 flex-1">
        <Button
          type="submit"
          variant="save"
          disabled={!ready}
          title={aiDefault ? (broke ? 'Saves without an AI line: no credits left' : 'Saves with an AI line, 1 credit') : 'Saves without an AI line'}
          className="h-11 flex-1 justify-center rounded-r-none px-5 text-[15px]"
        >
          <span className="max-sm:hidden">Save moment{playhead !== null && ' at'}</span><span className="sm:hidden">Save</span>{playhead !== null && <span className="tabular">{formatClock(playhead)}</span>}
          <kbd className={`${kbd} hidden border-saved-foreground/35 sm:inline`}>S</kbd>
        </Button>
        <Menu onOpenChange={open => { if (open) setMenuWidth(group.current?.offsetWidth); }}>
          <MenuTrigger asChild>
            <Button
              variant="save"
              disabled={!ready}
              aria-label="Choose how to save"
              className="h-11 rounded-l-none border-l border-saved-foreground/20 px-2.5"
            >
              <ChevronDown className="size-4" />
            </Button>
          </MenuTrigger>
          {/* As wide as the whole button, so the menu reads as part of it. */}
          <MenuContent className="min-w-64" style={{ width: menuWidth }}>
            <SaveOption label="With AI line" cost={aiCost} isDefault={aiDefault} onSelect={() => void capture(true)} />
            <SaveOption label="Without AI line" cost="Free" isDefault={!aiDefault} onSelect={() => void capture(false)} />
            <MenuSeparator />
            <MenuItem asChild className="text-xs text-muted-foreground">
              <Link to="/settings#account"><Settings className="size-4" />Change default in Settings</Link>
            </MenuItem>
          </MenuContent>
        </Menu>
      </div>
      {(
        <Button ref={noteButton} variant="secondary" size="icon" aria-label={noteOpen ? 'Edit note' : 'Add note'} aria-expanded={noteOpen} title={noteOpen ? 'Edit note' : 'Add note'}
          onClick={() => setNoteOpen(true)} className={cn('h-11 w-11 shrink-0', noteOpen && 'bg-muted')}>
          <SquarePen className="size-[18px]" />
        </Button>
      )}
    </form>
    </div>
  );
}
