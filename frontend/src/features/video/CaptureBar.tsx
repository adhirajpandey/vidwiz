import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { momentsApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { formatClock } from '../../lib/format';
import { momentKeys } from '../moments/queries';

/** Capture the current playback position, with an optional note and AI line. S saves from anywhere on the page. */
export default function CaptureBar({ videoId, currentTime, playhead, onCaptured }: {
  videoId: string;
  currentTime: () => number | null;
  /** Latest playback position, for the button label. */
  playhead: number | null;
  onCaptured?: (momentId: number) => void;
}) {
  const profile = useProfile();
  const [note, setNote] = useState('');
  const [ai, setAi] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();
  const notify = useNotify();
  const wantsAi = ai ?? profile.data?.ai_moments_default ?? false;
  const submit = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 's' || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, [contenteditable="true"], [role="dialog"]')) return;
      event.preventDefault();
      submit.current?.click();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const capture = async () => {
    const at = Math.floor(currentTime() ?? 0);
    setSaving(true);
    try {
      const result = await momentsApi.capture({
        video: videoId, at, note: note.trim() || null, ai: wantsAi, source: 'web',
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

  return (
    <form
      className="flex flex-col gap-2 sm:flex-row sm:items-center"
      onSubmit={event => { event.preventDefault(); void capture(); }}
    >
      <Input
        value={note}
        onChange={event => setNote(event.target.value)}
        placeholder="Note (optional)"
        aria-label="Note for this moment"
        className="sm:flex-1"
      />
      <div className="flex items-center gap-2">
        <label className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[9px] px-2 py-2 text-xs font-medium text-muted-foreground hover:bg-muted">
          <input type="checkbox" checked={wantsAi} onChange={event => setAi(event.target.checked)} className="accent-[hsl(var(--foreground))]" />
          <Sparkles className="size-3.5" />AI line, 1 credit
        </label>
        <Button ref={submit} type="submit" variant="save" disabled={saving} className="h-11 flex-1 px-5 text-[15px] sm:flex-none">
          Save moment{playhead !== null && <> at <span className="tabular">{formatClock(playhead)}</span></>}
          <kbd className="hidden rounded-[5px] border-[1.5px] border-saved-foreground/35 px-1.5 text-xs font-semibold sm:inline">S</kbd>
        </Button>
      </div>
    </form>
  );
}
