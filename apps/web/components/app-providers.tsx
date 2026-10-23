'use client';

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export type Locale = 'en' | 'es';
export type ThemePreference = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_THEME = 'sda-theme';
const STORAGE_LOCALE = 'sda-locale';

const messages = {
  en: {
    dashboard: 'Dashboard', projects: 'Projects', milestones: 'Milestones', releases: 'Releases', reports: 'Reports', baselines: 'Baselines', metrics: 'Metrics', risk: 'Risk', templates: 'Templates', teams: 'Teams', integrations: 'Integrations', settings: 'Settings',
    overview: 'Overview', requirements: 'Requirements', changes: 'Changes', verification: 'Verification', evidence: 'Evidence', signoff: 'Sign-off',
    search: 'Search...', share: 'Share', inSignoff: 'In Signoff', agreed: 'Agreed', pending: 'Pending', outOfScope: 'Out of scope', passed: 'Passed', failed: 'Failed', inProgress: 'In progress', rejected: 'Rejected', notStarted: 'Not started',
    release: 'Release 2.3 – Client Portal', version: 'Version 2.3.0', created: 'Created May 12, 2025', target: 'Target Sign-off May 30, 2025',
    topRequirements: 'Top Requirements', recentActivity: 'Recent Activity', verificationStatus: 'Verification Status', acceptanceCriteria: 'Acceptance Criteria', details: 'Details', viewVerification: 'View Verification',
    functional: 'Functional', high: 'High', userManagement: 'User Management', baseline: 'Baseline', owner: 'Owner', waitingApproval: 'Waiting for client approval',
    type: 'Type', priority: 'Priority', component: 'Component', createdLabel: 'Created', agreedLabel: 'Agreed', coverage: 'Coverage', status: 'Status',
    noResults: 'No requirements match your search.', settingsSoon: 'Settings', language: 'Language', theme: 'Theme', light: 'Light', dark: 'Dark', system: 'System', switchToLight: 'Switch to light mode', switchToDark: 'Switch to dark mode', close: 'Close', previous: 'Previous requirement', next: 'Next requirement',
    requirementCount: 'Requirements', verificationCount: 'Verification', changesCount: 'Changes', coverageCount: 'Coverage', vsLastRelease: 'vs last release',
  },
  es: {
    dashboard: 'Panel', projects: 'Proyectos', milestones: 'Hitos', releases: 'Entregas', reports: 'Informes', baselines: 'Líneas base', metrics: 'Métricas', risk: 'Riesgo', templates: 'Plantillas', teams: 'Equipos', integrations: 'Integraciones', settings: 'Configuración',
    overview: 'Resumen', requirements: 'Requisitos', changes: 'Cambios', verification: 'Verificación', evidence: 'Evidencia', signoff: 'Aprobación',
    search: 'Buscar...', share: 'Compartir', inSignoff: 'En aprobación', agreed: 'Acordado', pending: 'Pendiente', outOfScope: 'Fuera de alcance', passed: 'Superado', failed: 'Fallido', inProgress: 'En progreso', rejected: 'Rechazado', notStarted: 'No iniciado',
    release: 'Release 2.3 – Portal de cliente', version: 'Versión 2.3.0', created: 'Creado el 12 de mayo de 2025', target: 'Aprobación objetivo: 30 de mayo de 2025',
    topRequirements: 'Requisitos principales', recentActivity: 'Actividad reciente', verificationStatus: 'Estado de verificación', acceptanceCriteria: 'Criterios de aceptación', details: 'Detalles', viewVerification: 'Verificación',
    functional: 'Funcional', high: 'Alta', userManagement: 'Gestión de usuarios', baseline: 'Línea base', owner: 'Responsable', waitingApproval: 'Esperando aprobación del cliente',
    type: 'Tipo', priority: 'Prioridad', component: 'Componente', createdLabel: 'Creado', agreedLabel: 'Acordado', coverage: 'Cobertura', status: 'Estado',
    noResults: 'No hay requisitos que coincidan con la búsqueda.', settingsSoon: 'Configuración', language: 'Idioma', theme: 'Tema', light: 'Claro', dark: 'Oscuro', system: 'Sistema', switchToLight: 'Cambiar a modo claro', switchToDark: 'Cambiar a modo oscuro', close: 'Cerrar', previous: 'Requisito anterior', next: 'Requisito siguiente',
    requirementCount: 'Requisitos', verificationCount: 'Verificación', changesCount: 'Cambios', coverageCount: 'Cobertura', vsLastRelease: 'vs última entrega',
  },
} as const;

export type MessageKey = keyof typeof messages.en;

type PreferencesContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  themePreference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setThemePreference: (theme: ThemePreference) => void;
  t: (key: MessageKey) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } }));
  const [locale, setLocaleState] = useState<Locale>('en');
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>('dark');
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>('dark');

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const storedLocale = window.localStorage.getItem(STORAGE_LOCALE);
      if (storedLocale === 'es' || storedLocale === 'en') setLocaleState(storedLocale);
      else if (window.navigator.language.toLowerCase().startsWith('es')) setLocaleState('es');

      const storedTheme = window.localStorage.getItem(STORAGE_THEME);
      if (storedTheme === 'light' || storedTheme === 'system' || storedTheme === 'dark') setThemePreferenceState(storedTheme);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const update = () => setSystemTheme(media.matches ? 'dark' : 'light');
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  const resolvedTheme = themePreference === 'system' ? systemTheme : themePreference;

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.lang = locale;
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [locale, resolvedTheme]);

  function setLocale(localeValue: Locale) {
    setLocaleState(localeValue);
    window.localStorage.setItem(STORAGE_LOCALE, localeValue);
  }

  function setThemePreference(themeValue: ThemePreference) {
    setThemePreferenceState(themeValue);
    window.localStorage.setItem(STORAGE_THEME, themeValue);
  }

  const value = useMemo<PreferencesContextValue>(() => ({ locale, setLocale, themePreference, resolvedTheme, setThemePreference, t: (key) => messages[locale][key] }), [locale, themePreference, resolvedTheme]);
  return <QueryClientProvider client={queryClient}><PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider></QueryClientProvider>;
}

export function useAppPreferences() {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error('useAppPreferences must be used inside AppProviders');
  return value;
}
