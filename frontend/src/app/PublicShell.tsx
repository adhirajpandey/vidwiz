import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import Button from '../components/ui/Button';
import { Tooltip } from '../components/ui/Tooltip';

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight">
      <img src="/brand/vidwiz-mark-color.svg" alt="" className="size-7 rounded-[7px]" />
      <span>VidWiz</span>
    </Link>
  );
}

function SignedOutActions() {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex items-center gap-1">
      <Tooltip label={theme === 'dark' ? 'Light theme' : 'Dark theme'} side="bottom">
        <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={toggle}>
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
      </Tooltip>
      <Link to="/login" className="rounded-[9px] px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground">Log in</Link>
      <Link to="/signup" className="rounded-[9px] bg-accent px-3.5 py-2 text-sm font-semibold text-accent-foreground hover:opacity-90">Start free</Link>
    </div>
  );
}

export default function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4">
          <Logo />
          <div className="flex flex-1 justify-end gap-3"><SignedOutActions /></div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
