/**
 * Theme state, persisted.
 *
 * The initial value is already on `<html data-theme>` (set by an inline script in `index.html` before
 * first paint, so there is no flash). This hook reads it back, lets the user toggle, and writes the
 * choice to `localStorage` so it survives a reload.
 */
import { useCallback, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';
const KEY = 'travel-theme';

function current(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // A private-mode browser that refuses storage still gets a working toggle for the session.
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  return { theme, toggle };
}
