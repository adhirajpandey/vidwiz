import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BookmarkPlus, Sparkles } from 'lucide-react';
import { momentsApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { formatClock } from '../../lib/format';
import { momentKeys } from '../moments/queries';

/** Capture the current playback position, with an optional note and AI line. */
export default function CaptureBar({ videoId, currentTime, onCaptured }: {
  videoId: string;
  currentTime: () => number | null;
  onCaptured?: (momentId: number) => void;
}) {
  const profile = useProfile();
  const [note, setNote] = useState('');
  const [ai, setAi] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();
  const notify = useNotify();
  const wantsAi = ai ?? profile.data?.ai_moments_default ?? false;

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
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-2 text-xs text-muted-foreground hover:bg-muted">
          <input type="checkbox" checked={wantsAi} onChange={event => setAi(event.target.checked)} className="accent-[hsl(var(--accent))]" />
          <Sparkles className="size-3.5" />AI line · 1 credit
        </label>
        <Button type="submit" variant="primary" disabled={saving} className="flex-1 sm:flex-none">
          <BookmarkPlus className="size-4" />Capture
        </Button>
      </div>
    </form>
  );
}
