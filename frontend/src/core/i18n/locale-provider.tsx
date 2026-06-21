/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import { localeAtom } from "@/core/config/config";
import { isValidLocale } from "./browser-locale";

interface LocaleProviderProps {
  children: ReactNode;
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  const locale = useAtomValue(localeAtom);

  if (locale && isValidLocale(locale)) {
    return <I18nProvider locale={locale}>{children}</I18nProvider>;
  }

  return <I18nProvider>{children}</I18nProvider>;
};
