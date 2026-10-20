import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Settings } from 'lucide-react';
import { momentsApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../../components/ui/Menu';
import { formatClock } from '../../lib/format';
import { momentKeys } from '../moments/queries';

const kbd = 'rounded-[5px] border-[1.5px] px-1.5 text-xs font-semibold';

/**
 * Capture the current playback position with an optional note. Save follows the
 * AI line default from Settings; the arrow saves one moment the other way.
 * S saves from anywhere on the page, Shift S the other way.
 */
export default function CaptureBar({ videoId, currentTime, playhead, onCaptured }: {
  videoId: string;
  currentTime: () => number | null;
  /** Latest playback position, for the button label. */
  playhead: number | null;
  onCaptured?: (momentId: number) => void;
}) {
  const profile = useProfile();
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();
  const notify = useNotify();
  // Saving waits for the profile, so a save never guesses the AI line default.
  const ready = profile.data !== undefined && !saving;
  const aiDefault = profile.data?.ai_moments_default ?? false;

  const capture = async (ai: boolean) => {
    if (!ready) return;
    const at = Math.floor(currentTime() ?? 0);
    setSaving(true);
    try {
      const result = await momentsApi.capture({
        video: videoId, at, note: note.trim() || null, ai, source: 'web',
      });
      setNote('');
      void queryClient.invalidateQueries({ queryKey: momentKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['library'] });
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
      notify.success(result.merged ? 'Added to a nearby moment' : `Moment saved at ${formatClock(at)}`);
      onCaptured?.(result.moment.id);
    } catch (cause) {
      notify.error(cause, 'Moment not saved', 'The moment could not be saved.');
    } finally {
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
    <form
      className="flex flex-col gap-2 sm:flex-row sm:items-center"
      onSubmit={event => { event.preventDefault(); void capture(aiDefault); }}
    >
      <Input
        value={note}
        onChange={event => setNote(event.target.value)}
        placeholder="Note (optional)"
        aria-label="Note for this moment"
        className="sm:flex-1"
      />
      <div className="flex">
        <Button
          type="submit"
          variant="save"
          disabled={!ready}
          title={aiDefault ? 'Saves with an AI line, 1 credit' : 'Saves without an AI line'}
          className="h-11 flex-1 rounded-r-none px-5 text-[15px] sm:flex-none"
        >
          Save moment{playhead !== null && <> at <span className="tabular">{formatClock(playhead)}</span></>}
          <kbd className={`${kbd} hidden border-saved-foreground/35 sm:inline`}>S</kbd>
        </Button>
        <Menu>
          <MenuTrigger asChild>
            <Button
              variant="save"
              disabled={!ready}
              aria-label="More ways to save"
              className="h-11 rounded-l-none border-l border-saved-foreground/20 px-2.5"
            >
              <ChevronDown className="size-4" />
            </Button>
          </MenuTrigger>
          <MenuContent className="w-64">
            <MenuItem onSelect={() => void capture(!aiDefault)}>
              {aiDefault ? 'Save without AI line' : <span>Save with AI line<span className="text-muted-foreground">, 1 credit</span></span>}
              <kbd className={`${kbd} ml-auto hidden border-border text-muted-foreground sm:inline`}>Shift S</kbd>
            </MenuItem>
            <MenuSeparator />
            <MenuItem asChild className="text-xs text-muted-foreground">
              <Link to="/settings#account">
                <Settings className="size-3.5" />AI line {aiDefault ? 'on' : 'off'} by default
                <span className="ml-auto font-semibold text-foreground">Change</span>
              </Link>
            </MenuItem>
          </MenuContent>
        </Menu>
      </div>
    </form>
  );
}
