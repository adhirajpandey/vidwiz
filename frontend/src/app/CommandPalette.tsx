import { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import * as RadixDialog from '@radix-ui/react-dialog';
import { Library, PlayCircle, Search, Settings, Sparkles } from 'lucide-react';
import { extractVideoId } from '../lib/videoUtils';

/** ⌘K / Ctrl+K: search, open a pasted YouTube link, or jump to a page. */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(value => !value);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const go = (path: string) => {
    setOpen(false);
    setQuery('');
    navigate(path);
  };
  const trimmed = query.trim();
  const videoId = extractVideoId(trimmed);

  return (
    <RadixDialog.Root open={open} onOpenChange={setOpen}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <RadixDialog.Content className="fixed left-1/2 top-[15vh] z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-card shadow-[0_30px_80px_rgb(0_0_0/0.25)]">
          <RadixDialog.Title className="sr-only">Command palette</RadixDialog.Title>
          <Command label="Command palette" shouldFilter={false}>
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="size-4 text-muted-foreground" />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Search, paste a YouTube link, or go to…"
                className="h-14 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
              />
            </div>
            <Command.List className="max-h-80 overflow-y-auto p-2 text-sm">
              {videoId && (
                <Command.Item onSelect={() => go(`/v/${videoId}`)} className="palette-item">
                  <PlayCircle className="size-4" />Open video {videoId}
                </Command.Item>
              )}
              {trimmed.length >= 2 && !videoId && (
                <>
                  <Command.Item onSelect={() => go(`/search?q=${encodeURIComponent(trimmed)}`)} className="palette-item">
                    <Search className="size-4" />Search for “{trimmed}”
                  </Command.Item>
                  <Command.Item onSelect={() => go(`/ask?q=${encodeURIComponent(trimmed)}`)} className="palette-item">
                    <Sparkles className="size-4" />Ask your library “{trimmed}”
                  </Command.Item>
                </>
              )}
              <Command.Group heading="Go to" className="mt-1 text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
                <Command.Item onSelect={() => go('/library')} className="palette-item"><Library className="size-4" />Library</Command.Item>
                <Command.Item onSelect={() => go('/ask')} className="palette-item"><Sparkles className="size-4" />Ask your library</Command.Item>
                <Command.Item onSelect={() => go('/settings')} className="palette-item"><Settings className="size-4" />Settings</Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
