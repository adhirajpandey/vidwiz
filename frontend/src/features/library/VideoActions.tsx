import { useRef, useState } from 'react';
import { MoreHorizontal, Trash2 } from 'lucide-react';
import type { LibraryVideo } from '../../api';
import { normalizeApiError } from '../../api/errors';
import Button from '../../components/ui/Button';
import { Dialog, DialogContent } from '../../components/ui/Dialog';
import { Menu, MenuContent, MenuItem, MenuTrigger } from '../../components/ui/Menu';
import { Tooltip } from '../../components/ui/Tooltip';
import { useNotify } from '../../hooks/useNotify';
import { plural } from '../../lib/format';
import { useRemoveVideo } from './queries';

function consequence(video: LibraryVideo): string {
  const items = [
    video.moment_count > 0 ? plural(video.moment_count, 'moment') : null,
    video.chat_count > 0 ? plural(video.chat_count, 'chat') : null,
  ].filter(Boolean);
  if (items.length === 0) return 'This removes the video from your library.';
  return `This permanently deletes your ${items.join(' and ')} for this video. You can't undo this.`;
}

export default function VideoActions({ video }: { video: LibraryVideo }) {
  const remove = useRemoveVideo();
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actionsButton = useRef<HTMLButtonElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);

  const changeOpen = (next: boolean) => {
    if (remove.isPending) return;
    setError(null);
    setOpen(next);
  };
  const reallyDelete = () => {
    setError(null);
    remove.mutate(video.video_id, {
      onSuccess: () => { setOpen(false); notify.success('Video deleted'); },
      onError: cause => setError(normalizeApiError(cause, 'The video could not be deleted.').message),
    });
  };

  return (
    <>
      <Menu>
        <Tooltip label="Video actions">
          <MenuTrigger asChild>
            <Button ref={actionsButton} variant="ghost" size="icon" aria-label="Video actions" className="opacity-60 group-hover:opacity-100">
              <MoreHorizontal className="size-4" />
            </Button>
          </MenuTrigger>
        </Tooltip>
        <MenuContent onCloseAutoFocus={event => { if (open) event.preventDefault(); }}>
          <MenuItem className="text-destructive" onSelect={() => changeOpen(true)}>
            <Trash2 className="size-4" />Delete
          </MenuItem>
        </MenuContent>
      </Menu>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent
          title="Delete this video?"
          description={consequence(video)}
          onOpenAutoFocus={event => { event.preventDefault(); cancelButton.current?.focus(); }}
          onCloseAutoFocus={event => { event.preventDefault(); actionsButton.current?.focus(); }}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={remove.isPending} onClick={reallyDelete} className="border-0 bg-destructive text-background hover:bg-destructive hover:brightness-105">Delete</Button>
            <Button ref={cancelButton} size="sm" variant="ghost" disabled={remove.isPending} onClick={() => changeOpen(false)}>Cancel</Button>
            {error && <p role="alert" className="w-full text-xs text-destructive">{error}</p>}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
