import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { cn } from '../lib/utils';

export default function SearchForm({ className, shortcut = false }: { className?: string; shortcut?: boolean }) {
  const navigate = useNavigate();
  const location = useLocation();
  const current = location.pathname === '/search' ? new URLSearchParams(location.search).get('q') ?? '' : '';
  const [value, setValue] = useState(current);
  useEffect(() => setValue(current), [current]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const q = value.trim();
    if (q.length >= 2) navigate(`/search?q=${encodeURIComponent(q)}`);
  };
  return (
    <form role="search" onSubmit={submit} className={cn('relative w-full', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        enterKeyHint="search"
        value={value}
        onChange={event => setValue(event.target.value)}
        aria-label="Search your moments and videos"
        placeholder="Search moments and transcripts"
        className={cn(
          'h-10 w-full rounded-[9px] border border-input bg-card pl-9 text-sm placeholder:text-muted-foreground focus:border-foreground/60',
          shortcut ? 'pr-14' : 'pr-3',
        )}
      />
      {shortcut && (
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded-[5px] border border-border border-b-2 px-1.5 text-[11px] font-semibold text-muted-foreground">Ctrl K</kbd>
      )}
    </form>
  );
}
