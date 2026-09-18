import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { COPY, LOCALES, readLocale, writeLocale, type Copy, type Locale } from "./i18n";

type Ctx = { locale: Locale; t: Copy; setLocale: (locale: Locale) => void; locales: typeof LOCALES };

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => (typeof window === "undefined" ? "en" : readLocale()));
  // index.html hardcodes <html lang="en">, and writeLocale only runs on an explicit
  // switch — so a French browser or a stored locale rendered translated copy that still
  // claimed to be English to screen readers and crawlers.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const value = useMemo<Ctx>(
    () => ({
      locale,
      t: COPY[locale],
      locales: LOCALES,
      setLocale: (next) => {
        writeLocale(next);
        setLocaleState(next);
      },
    }),
    [locale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("I18nProvider missing");
  return ctx;
}
