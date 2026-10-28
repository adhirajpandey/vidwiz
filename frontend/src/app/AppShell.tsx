import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Home, LifeBuoy, Library, LogOut, Moon, Search, Settings, Sparkles, Sun } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useProfile } from '../hooks/useProfile';
import { useSignedIn } from '../hooks/useSignedIn';
import { useTheme } from '../hooks/useTheme';
import { removeToken } from '../lib/authUtils';
import { cn } from '../lib/utils';
import Button from '../components/ui/Button';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../components/ui/Menu';
import SearchForm from '../components/SearchForm';
import { Tooltip } from '../components/ui/Tooltip';
const CommandPalette = lazy(() => import('./CommandPalette'));

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/library', label: 'Library', icon: Library, end: false },
  { to: '/ask', label: 'Ask', icon: Sparkles, end: false },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight">
      <img src="/brand/vidwiz-mark-color.svg" alt="" className="size-7 rounded-[7px]" />
      <span>VidWiz</span>
    </Link>
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
      <Tooltip label={name} side="bottom">
      <MenuTrigger asChild>
        <button type="button" aria-label="Account menu" className="flex items-center gap-2 rounded-lg p-1 hover:bg-muted">
          {profile.data?.profile_image_url ? (
            <img src={profile.data.profile_image_url} alt="" className="size-7 rounded-full" referrerPolicy="no-referrer" />
          ) : (
            <span className="flex size-8 items-center justify-center rounded-full bg-foreground text-xs font-bold text-background">
              {name.slice(0, 1).toUpperCase()}
            </span>
          )}
        </button>
      </MenuTrigger>
      </Tooltip>
      <MenuContent className="w-60">
        <div className="px-2.5 py-2">
          <p className="truncate text-sm font-medium">{name}</p>
          <p className="text-xs text-muted-foreground tabular">
            {profile.data ? `${profile.data.credits_balance} credits` : 'Loading credits…'}
          </p>
        </div>
        <MenuSeparator />
        <MenuItem onSelect={() => navigate('/settings')}><Settings className="size-4" />Settings</MenuItem>
        <MenuItem onSelect={() => navigate('/support')}><LifeBuoy className="size-4" />Help</MenuItem>
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

function MobileNav() {
  const items = [...NAV, { to: '/search', label: 'Search', icon: Search, end: false }, { to: '/settings', label: 'Settings', icon: Settings, end: false }];
  return (
    <nav aria-label="Primary" className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface md:hidden">
      <ul className="grid grid-cols-5">
        {items.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) => cn('relative flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold', isActive ? 'text-foreground before:absolute before:inset-x-5 before:top-0 before:h-0.5 before:rounded-full before:bg-foreground' : 'text-muted-foreground')}
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
      <header className="sticky top-0 z-40 bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4">
          <Logo />
          {signedIn && (
            <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
              {NAV.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) => cn('rounded-[9px] px-3 py-1.5 text-sm font-semibold', isActive ? 'bg-card text-foreground shadow-[inset_0_0_0_1px_hsl(var(--border))]' : 'text-muted-foreground hover:text-foreground')}
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="flex flex-1 justify-end gap-3">
            {signedIn && <SearchForm shortcut className="hidden max-w-md md:block" />}
            {signedIn ? <UserMenu /> : <SignedOutActions />}
          </div>
        </div>
      </header>
      <main className={cn('mx-auto max-w-6xl px-4 py-8', signedIn && 'pb-24 md:pb-12')}>{children}</main>
      {signedIn && <MobileNav />}
      {signedIn && <Suspense fallback={null}><CommandPalette /></Suspense>}
    </div>
  );
}
