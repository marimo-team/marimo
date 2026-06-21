/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import { localeAtom } from "@/core/config/config";

interface LocaleProviderProps {
  children: ReactNode;
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  const locale = useAtomValue(localeAtom);

  return <I18nProvider locale={safeLocale(locale)}>{children}</I18nProvider>;
};

const DEFAULT_LOCALE = "en-US";

function safeLocale(locale: string | null | undefined) {
  if (locale && isValidLocale(locale)) {
    return locale;
  }
  return browserLocale();
}

function browserLocale() {
  const language = navigator.language;
  if (language && isValidLocale(language)) {
    return language;
  }
  return DEFAULT_LOCALE;
}

function isValidLocale(locale: string) {
  try {
    new Intl.NumberFormat(locale);
    return true;
  } catch {
    return false;
  }
}
