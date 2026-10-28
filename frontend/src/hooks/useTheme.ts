import { useCallback, useEffect, useState } from 'react';
import { useHydrated } from './useHydrated';

type Theme = 'light' | 'dark';

function initialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  try {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* storage unavailable */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function useTheme() {
  const hydrated = useHydrated();
  const [preferredTheme, setTheme] = useState<Theme>(initialTheme);
  const theme = hydrated ? preferredTheme : 'light';
  useEffect(() => {
    if (!hydrated) return;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try { localStorage.setItem('theme', theme); } catch { /* storage unavailable */ }
  }, [hydrated, theme]);
  const toggle = useCallback(() => setTheme(value => (value === 'dark' ? 'light' : 'dark')), []);
  return { theme, toggle };
}
