import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Home, Library, LogOut, Moon, Search, Settings, Sparkles, Sun } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useProfile } from '../hooks/useProfile';
import { useSignedIn } from '../hooks/useSignedIn';
import { useTheme } from '../hooks/useTheme';
import { removeToken } from '../lib/authUtils';
import { cn } from '../lib/utils';
import Button from '../components/ui/Button';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../components/ui/Menu';
import CommandPalette from './CommandPalette';

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/library', label: 'Library', icon: Library, end: false },
  { to: '/ask', label: 'Ask', icon: Sparkles, end: false },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <img src="/icon-192.png" alt="" className="size-7 rounded-md" />
      <span>VidWiz</span>
    </Link>
  );
}

function HeaderSearch() {
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
    <form role="search" onSubmit={submit} className="relative hidden w-full max-w-md md:block">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={value}
        onChange={event => setValue(event.target.value)}
        aria-label="Search your moments and videos"
        placeholder="Search moments and transcripts"
        className="h-9 w-full rounded-lg border border-input bg-surface pl-9 pr-14 text-sm placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-border px-1.5 font-mono text-[10px] text-muted-foreground">⌘K</kbd>
    </form>
  );
}

function UserMenu() {
  const profile = useProfile();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const name = profile.data?.name || profile.data?.email || 'Account';
  const logout = () => {
    removeToken();
    queryClient.clear();
    navigate('/');
  };
  return (
    <Menu>
      <MenuTrigger asChild>
        <button type="button" aria-label="Account menu" className="flex items-center gap-2 rounded-lg p-1 hover:bg-muted">
          {profile.data?.profile_image_url ? (
            <img src={profile.data.profile_image_url} alt="" className="size-7 rounded-full" referrerPolicy="no-referrer" />
          ) : (
            <span className="flex size-7 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
              {name.slice(0, 1).toUpperCase()}
            </span>
          )}
        </button>
      </MenuTrigger>
      <MenuContent className="w-60">
        <div className="px-2.5 py-2">
          <p className="truncate text-sm font-medium">{name}</p>
          <p className="text-xs text-muted-foreground tabular">
            {profile.data ? `${profile.data.credits_balance} credits` : 'Loading credits…'}
          </p>
        </div>
        <MenuSeparator />
        <MenuItem onSelect={() => navigate('/settings')}><Settings className="size-4" />Settings</MenuItem>
        <MenuItem onSelect={toggle}>
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          {theme === 'dark' ? 'Light theme' : 'Dark theme'}
        </MenuItem>
        <MenuSeparator />
        <MenuItem onSelect={logout}><LogOut className="size-4" />Log out</MenuItem>
      </MenuContent>
    </Menu>
  );
}

function SignedOutActions() {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex items-center gap-1">
      <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={toggle}>
        {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </Button>
      <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">Log in</Link>
      <Link to="/signup" className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-foreground hover:opacity-90">Sign up</Link>
    </div>
  );
}

function MobileNav() {
  const items = [...NAV, { to: '/search', label: 'Search', icon: Search, end: false }, { to: '/settings', label: 'Settings', icon: Settings, end: false }];
  return (
    <nav aria-label="Primary" className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur md:hidden">
      <ul className="grid grid-cols-5">
        {items.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) => cn('flex flex-col items-center gap-0.5 py-2 text-[11px]', isActive ? 'text-accent' : 'text-muted-foreground')}
            >
              <Icon className="size-5" />{label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const signedIn = useSignedIn();
  const { pathname } = useLocation();
  // The signed-out landing page brings its own header and full-width sections.
  if (!signedIn && pathname === '/') return children;
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <Logo />
          {signedIn && (
            <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
              {NAV.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) => cn('rounded-lg px-3 py-1.5 text-sm font-medium', isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground')}
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="flex flex-1 justify-end gap-3">
            {signedIn && <HeaderSearch />}
            {signedIn ? <UserMenu /> : <SignedOutActions />}
          </div>
        </div>
      </header>
      <main className={cn('mx-auto max-w-6xl px-4 py-6', signedIn && 'pb-24 md:pb-10')}>{children}</main>
      {signedIn && <MobileNav />}
      {signedIn && <CommandPalette />}
    </div>
  );
}
