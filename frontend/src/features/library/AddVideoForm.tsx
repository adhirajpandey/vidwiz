import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { libraryApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { extractVideoId } from '../../lib/videoUtils';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

/** Paste a YouTube link: the video is saved and opened. */
export default function AddVideoForm({ autoFocus = false }: { autoFocus?: boolean }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notify = useNotify();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const videoId = extractVideoId(value);
    if (!videoId) {
      setError('Paste a YouTube video link, like youtube.com/watch?v=… or youtu.be/…');
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await libraryApi.save(videoId);
      void queryClient.invalidateQueries({ queryKey: ['library'] });
      navigate(`/v/${videoId}`);
    } catch (cause) {
      notify.error(cause, 'Video not saved', 'The video could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-1.5">
      <div className="flex gap-2">
        <Input
          value={value}
          onChange={event => { setValue(event.target.value); setError(null); }}
          placeholder="Paste a YouTube link"
          aria-label="YouTube link"
          aria-invalid={Boolean(error)}
          autoFocus={autoFocus}
        />
        <Button type="submit" variant="primary" disabled={saving || !value.trim()}>
          <Plus className="size-4" />Add
        </Button>
      </div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </form>
  );
}
