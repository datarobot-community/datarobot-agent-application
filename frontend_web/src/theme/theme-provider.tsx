'use client';

import { useCurrentUser } from '@/api/auth/hooks';
import { useState, createContext, useContext, useLayoutEffect, useEffect, useMemo } from 'react';

export type Theme = 'light' | 'dark';
export type UserTheme = Theme | 'system';

interface ThemeContextType {
  theme: Theme;
  userTheme: UserTheme;
}

const PREFERS_COLOR_SCHEME_DARK = '(prefers-color-scheme: dark)';
const themeKey = 'app-theme';

const ThemeContext = createContext<ThemeContextType>({
  theme: 'light',
  userTheme: 'system',
});

export const useTheme = () => useContext(ThemeContext);

function useSystemTheme(): Theme {
  const [systemTheme, setSystemTheme] = useState<Theme>(() =>
    typeof window !== 'undefined' && window.matchMedia(PREFERS_COLOR_SCHEME_DARK).matches
      ? 'dark'
      : 'light'
  );

  useEffect(() => {
    const query = window.matchMedia(PREFERS_COLOR_SCHEME_DARK);
    const handler = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? 'dark' : 'light');
    };
    query.addEventListener('change', handler);
    return () => query.removeEventListener('change', handler);
  }, []);

  return systemTheme;
}

const getInitialTheme = (systemTheme: Theme): Theme => {
  if (typeof window === 'undefined') return 'light';
  const saved = localStorage.getItem(themeKey);
  if (saved === 'light' || saved === 'dark') {
    return saved;
  }
  return systemTheme;
};

export const ThemeProvider = ({
  children,
}: {
  children: React.ReactNode | ((props: { theme: Theme }) => React.ReactNode);
}) => {
  const { data: user } = useCurrentUser();
  const systemTheme = useSystemTheme();

  const theme = useMemo<Theme>(() => {
    if (user?.theme === 'system') return systemTheme;
    if (user?.theme === 'light' || user?.theme === 'dark') return user.theme;
    return getInitialTheme(systemTheme);
  }, [user?.theme, systemTheme]);

  const userTheme: UserTheme = user?.theme ?? 'system';

  useLayoutEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    if (user?.theme) {
      localStorage.setItem(themeKey, user.theme);
    }
  }, [user?.theme]);

  const value = useMemo(() => ({ theme, userTheme }), [theme, userTheme]);

  return (
    <ThemeContext.Provider value={value}>
      {typeof children === 'function' ? children({ theme }) : children}
    </ThemeContext.Provider>
  );
};
